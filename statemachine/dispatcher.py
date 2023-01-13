# coding: utf-8
import inspect
from collections import namedtuple
from functools import wraps
from operator import attrgetter

from .exceptions import AttrNotFound
from .utils import ugettext as _


class ObjectConfig(namedtuple("ObjectConfig", "obj skip_attrs")):
    """Configuration for objects passed to resolver_factory.

    Args:
        obj: Any object that will serve as lookup for attributes.
        skip_attrs: Protected attrs that will be ignored on the search.
    """

    @classmethod
    def from_obj(cls, obj):
        if isinstance(obj, ObjectConfig):
            return obj
        else:
            return cls(obj, set())


def methodcaller(method):
    """Build a wrapper that adapts the received arguments to the inner method signature"""

    # spec is a named tuple ArgSpec(args, varargs, keywords, defaults)
    # args is a list of the argument names (it may contain nested lists)
    # varargs and keywords are the names of the * and ** arguments or None
    # defaults is a tuple of default argument values or None if there are no default arguments
    try:
        spec = inspect.getfullargspec(method)
    except AttributeError:  # pragma: no cover
        spec = inspect.getargspec(method)
    keywords = getattr(spec, "varkw", getattr(spec, "keywords", None))
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


def _get_func_by_attr(attr, *configs):
    for config in configs:
        if attr in config.skip_attrs:
            continue
        func = getattr(config.obj, attr, None)
        if func is not None:
            break
    else:
        raise AttrNotFound(
            _("Did not found name '{}' from model or statemachine").format(attr)
        )
    return func, config.obj


def ensure_callable(attr, *objects):
    """Ensure that `attr` is a callable, if not, tries to retrieve one from any of the given
    `objects`.

    Args:
        attr (str or callable): A property/method name or a callable.
        objects: A list of objects instances that will serve as lookup for the given attr.
            The result `callable`, if any, will be a wrapper to the first object's attr that
            has the given ``attr``.
    """
    if callable(attr) or isinstance(attr, property):
        return methodcaller(attr)

    # Setup configuration if not present to normalize the internal API
    configs = [ObjectConfig.from_obj(obj) for obj in objects]

    func, obj = _get_func_by_attr(attr, *configs)

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
    """Factory that returns a configured resolver."""

    @wraps(ensure_callable)
    def wrapper(attr):
        return ensure_callable(attr, *objects)

    return wrapper
