from collections import namedtuple
from operator import attrgetter
from typing import Any

from .signature import SignatureAdapter


class ObjectConfig(namedtuple("ObjectConfig", "obj skip_attrs resolver_id")):
    """Configuration for objects passed to resolver_factory.

    Args:
        obj: Any object that will serve as lookup for attributes.
        skip_attrs: Protected attrs that will be ignored on the search.
    """

    @classmethod
    def from_obj(cls, obj, skip_attrs=None):
        if isinstance(obj, ObjectConfig):
            return obj
        else:
            return cls(obj, set(skip_attrs) if skip_attrs else set(), str(id(obj)))

    def getattr(self, attr):
        if attr in self.skip_attrs:
            return
        return getattr(self.obj, attr, None)


class WrapSearchResult:
    is_empty = False

    def __init__(self, attribute, resolver_id) -> None:
        self.attribute = attribute
        self.resolver_id = resolver_id
        self._cache = None
        self.unique_key = f"{attribute}@{resolver_id}"

    def __repr__(self):
        return f"{type(self).__name__}({self.unique_key})"

    def wrap(self):  # pragma: no cover
        pass

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        if self._cache is None:
            self._cache = self.wrap()
        assert self._cache
        return self._cache(*args, **kwds)


class EmptyWrapSearchResult(WrapSearchResult):
    is_empty = True


class CallableSearchResult(WrapSearchResult):
    def __init__(self, attribute, a_callable, resolver_id) -> None:
        self.a_callable = a_callable
        super().__init__(attribute, resolver_id)

    def wrap(self):
        return SignatureAdapter.wrap(self.a_callable)


class AttributeCallableSearchResult(WrapSearchResult):
    def __init__(self, attribute, obj, resolver_id) -> None:
        self.obj = obj
        super().__init__(attribute, resolver_id)

    def wrap(self):
        # if `attr` is not callable, then it's an attribute or property,
        # so `func` contains it's current value.
        # we'll build a method that get's the fresh value for each call
        getter = attrgetter(self.attribute)

        def wrapper(*args, **kwargs):
            return getter(self.obj)

        return wrapper


class EventSearchResult(WrapSearchResult):
    def __init__(self, attribute, func, resolver_id) -> None:
        self.func = func
        super().__init__(attribute, resolver_id)

    def wrap(self):
        "Events already have the 'machine' parameter defined."

        def wrapper(*args, **kwargs):
            kwargs.pop("machine", None)
            return self.func(*args, **kwargs)

        return wrapper


def search_callable(attr, *configs) -> WrapSearchResult:
    if callable(attr) or isinstance(attr, property):
        return CallableSearchResult(attr, attr, None)

    for config in configs:
        func = config.getattr(attr)
        if func is not None:
            if not callable(func):
                return AttributeCallableSearchResult(
                    attr, config.obj, config.resolver_id
                )

            if getattr(func, "_is_sm_event", False):
                return EventSearchResult(attr, func, config.resolver_id)

            return CallableSearchResult(attr, func, config.resolver_id)

    return EmptyWrapSearchResult(attr, None)


def resolver_factory(*objects):
    """Factory that returns a configured resolver."""

    objects = [ObjectConfig.from_obj(obj) for obj in objects]

    def wrapper(attr):
        return search_callable(attr, *objects)

    return wrapper
