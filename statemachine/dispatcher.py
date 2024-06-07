from collections import namedtuple
from operator import attrgetter
from typing import Any
from typing import Generator
from typing import Tuple

from .signature import SignatureAdapter


class ObjectConfig(namedtuple("ObjectConfig", "obj skip_attrs resolver_id")):
    """Configuration for objects passed to resolver_factory.

    Args:
        obj: Any object that will serve as lookup for attributes.
        skip_attrs: Protected attrs that will be ignored on the search.
    """

    @classmethod
    def from_obj(cls, obj, skip_attrs=None) -> "ObjectConfig":
        if isinstance(obj, ObjectConfig):
            return obj
        else:
            return cls(obj, skip_attrs or set(), str(id(obj)))


class WrapSearchResult:
    def __init__(self, attribute, resolver_id) -> None:
        self.attribute = attribute
        self.resolver_id = resolver_id
        self._cache = None
        self.unique_key = f"{attribute}@{resolver_id}"

    def __repr__(self):
        return f"{type(self).__name__}({self.unique_key})"

    def wrap(self):  # pragma: no cover
        pass

    async def __call__(self, *args: Any, **kwds: Any) -> Any:
        if self._cache is None:
            self._cache = self.wrap()
        assert self._cache
        return await self._cache(*args, **kwds)


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

        async def wrapper(*args, **kwargs):
            return getter(self.obj)

        return wrapper


class EventSearchResult(WrapSearchResult):
    def __init__(self, attribute, func, resolver_id) -> None:
        self.func = func
        super().__init__(attribute, resolver_id)

    def wrap(self):
        "Events already have the 'machine' parameter defined."

        async def wrapper(*args, **kwargs):
            kwargs.pop("machine", None)
            return await self.func(*args, **kwargs)

        return wrapper


def _search_callable_attr_is_property(
    attr, configs: Tuple[ObjectConfig, ...]
) -> "WrapSearchResult | None":
    # if the attr is a property, we'll try to find the object that has the
    # property on the configs
    attr_name = attr.fget.__name__
    for obj, _skip_attrs, resolver_id in configs:
        func = getattr(type(obj), attr_name, None)
        if func is not None and func is attr:
            return AttributeCallableSearchResult(attr_name, obj, resolver_id)
    return None


def _search_callable_attr_is_callable(attr, configs: Tuple[ObjectConfig, ...]) -> WrapSearchResult:
    # if the attr is an unbounded method, we'll try to find the bounded method
    # on the configs
    if not hasattr(attr, "__self__"):
        for obj, _skip_attrs, resolver_id in configs:
            func = getattr(obj, attr.__name__, None)
            if func is not None and func.__func__ is attr:
                return CallableSearchResult(attr.__name__, func, resolver_id)

    return CallableSearchResult(attr, attr, None)


def _search_callable_in_configs(
    attr, configs: Tuple[ObjectConfig, ...]
) -> Generator[WrapSearchResult, None, None]:
    for obj, skip_attrs, resolver_id in configs:
        if attr in skip_attrs:
            continue

        if not hasattr(obj, attr):
            continue

        func = getattr(obj, attr)
        if not callable(func):
            yield AttributeCallableSearchResult(attr, obj, resolver_id)

        if getattr(func, "_is_sm_event", False):
            yield EventSearchResult(attr, func, resolver_id)

        yield CallableSearchResult(attr, func, resolver_id)


def search_callable(
    attr, configs: Tuple[ObjectConfig, ...]
) -> Generator[WrapSearchResult, None, None]:  # noqa: C901
    if isinstance(attr, property):
        result = _search_callable_attr_is_property(attr, configs)
        if result is not None:
            yield result
        return

    if callable(attr):
        yield _search_callable_attr_is_callable(attr, configs)
        return

    yield from _search_callable_in_configs(attr, configs)


def resolver_factory(objects: Tuple[ObjectConfig, ...]):
    """Factory that returns a configured resolver."""

    def resolver(attr) -> Generator[WrapSearchResult, None, None]:
        yield from search_callable(attr, objects)

    return resolver


def resolver_factory_from_objects(*objects: Tuple[Any, ...]):
    configs: Tuple[ObjectConfig, ...] = tuple(ObjectConfig.from_obj(o) for o in objects)
    return resolver_factory(configs)
