# coding: utf-8

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
                _("Callback {!r} not property configured.").format(self)
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
    def __init__(self, resolver=None, factory=CallbackWrapper):
        self.items = []
        self._resolver = resolver
        self.factory = factory

    def __repr__(self):
        return "{}({!r}, factory={!r})".format(
            type(self).__name__, self.items, self.factory
        )

    def setup(self, resolver):
        """Validate configuracions"""
        self._resolver = resolver
        self.items = [
            callback for callback in self.items if callback.setup(self._resolver)
        ]

    def __call__(self, *args, **kwargs):
        return [callback(*args, **kwargs) for callback in self.items]

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def add(self, callbacks, **kwargs):
        if callbacks is None:
            return self

        unprepared = ensure_iterable(callbacks)
        for func in unprepared:
            if func in self.items:
                continue
            callback = self.factory(func, **kwargs)

            if self._resolver is not None and not callback.setup(self._resolver):
                continue

            self.items.append(callback)

        return self
