from collections import namedtuple
from functools import wraps
from operator import attrgetter

from .exceptions import AttrNotFound
from .i18n import _
from .signature import SignatureAdapter


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
        return SignatureAdapter.wrap(attr)

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

    if getattr(func, "_is_sm_event", False):
        "Events already have the 'machine' parameter defined."

        def wrapper(*args, **kwargs):
            kwargs.pop("machine")
            return func(*args, **kwargs)

        return wrapper

    return SignatureAdapter.wrap(func)


def resolver_factory(*objects):
    """Factory that returns a configured resolver."""

    @wraps(ensure_callable)
    def wrapper(attr):
        return ensure_callable(attr, *objects)

    return wrapper
