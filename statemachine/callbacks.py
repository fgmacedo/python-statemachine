# coding: utf-8
import inspect
from functools import wraps
from operator import attrgetter

from .utils import ugettext as _, ensure_iterable
from .exceptions import InvalidDefinition, AttrNotFound


class CallbackWrapper(object):
    """A thin wrapper that ensures the targef callback is a proper callable.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(self, func, suppress_errors=False):
        self.func = func
        self.suppress_errors = suppress_errors
        self._callback = None

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.func)

    def __eq__(self, other):
        return self.func == getattr(other, "func", other)

    def setup(self, resolver):
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        try:
            self._callback = resolver(self.func)
            return True
        except AttrNotFound:
            if not self.suppress_errors:
                raise
            return False

    def __call__(self, *args, **kwargs):
        if self._callback is None:
            raise InvalidDefinition(
                "Callback {!r} not property configured.".format(self)
            )
        return self._callback(*args, **kwargs)


class ConditionWrapper(CallbackWrapper):
    def __init__(self, func, suppress_errors=False, expected_value=True):
        super(ConditionWrapper, self).__init__(func, suppress_errors)
        self.expected_value = expected_value

    def __call__(self, *args, **kwargs):
        return (
            super(ConditionWrapper, self).__call__(*args, **kwargs)
            == self.expected_value
        )


class Callbacks(object):
    def __init__(self, factory=CallbackWrapper):
        self.items = []
        self.factory = factory

    def __repr__(self):
        return "{}({!r}, factory={!r})".format(
            type(self).__name__, self.items, self.factory
        )

    def setup(self, resolver):
        """Validate configuracions"""
        self.items = [callback for callback in self.items if callback.setup(resolver)]

    def __call__(self, *args, **kwargs):
        return [callback(*args, **kwargs) for callback in self.items]

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def add(self, callbacks, resolver=None, **kwargs):
        if callbacks is None:
            return self

        unprepared = ensure_iterable(callbacks)
        for func in unprepared:
            if func in self.items:
                continue
            callback = self.factory(func, **kwargs)

            if resolver is not None and not callback.setup(resolver):
                continue

            self.items.append(callback)

        return self


def methodcaller(method):
    """Build a wrapper that addapts the received arguments to the inner method signature"""

    # spec is a named tuple ArgSpec(args, varargs, keywords, defaults)
    # args is a list of the argument names (it may contain nested lists)
    # varargs and keywords are the names of the * and ** arguments or None
    # defaults is a tuple of default argument values or None if there are no default arguments
    spec = inspect.getargspec(method)
    keywords = spec.keywords
    expected_args = list(spec.args)
    expected_kwargs = spec.defaults or {}

    # discart "self" argument for bounded methods
    if hasattr(method, "__self__") and expected_args and expected_args[0] == "self":
        expected_args = expected_args[1:]

    @wraps(method)
    def wrapper(*args, **kwargs):
        if spec.varargs is not None:
            filtered_args = args
        else:
            filtered_args = [
                kwargs.get(k, (args[idx] if idx < len(args) else None))
                for idx, k in enumerate(expected_args)
            ]

        if keywords is not None:
            filtered_kwargs = kwargs
        else:
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in expected_kwargs}

        return method(*filtered_args, **filtered_kwargs)

    return wrapper


def _get_func_by_attr(attr, *objects):
    for obj in objects:
        func = getattr(obj, attr, None)
        if func is not None:
            break
    else:
        raise AttrNotFound(
            _("Did not found name '{}' from model or statemachine".format(attr))
        )
    return func, obj


def ensure_callable(attr, *objects):
    """Ensure that `attr` is a callable, if not, tries to retrieve one from any of the given
    `objects`.

    Args:
        attr (str or callable): A property/method name or a callable.
    """
    if callable(attr) or isinstance(attr, property):
        return methodcaller(attr)

    func, obj = _get_func_by_attr(attr, *objects)

    if not callable(func):
        # if `attr` is not callable, then it's an attribute or property,
        # so `func` contains it's current value.
        # we'll build a method that get's the fresh value for each call
        getter = attrgetter(attr)

        def wrapper(*args, **kwargs):
            return getter(obj)

        return wrapper

    return methodcaller(func)


def resolver_factory(*objects):
    @wraps(ensure_callable)
    def wrapper(attr):
        return ensure_callable(attr, *objects)

    return wrapper
