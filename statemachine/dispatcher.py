from collections import namedtuple
from operator import attrgetter
from typing import Any
from typing import Generator
from typing import Iterable
from typing import Tuple

from .signature import SignatureAdapter


class ObjectConfig(namedtuple("ObjectConfig", "obj all_attrs resolver_id")):
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
            if skip_attrs is None:
                skip_attrs = set()
            all_attrs = set(dir(obj)) - skip_attrs
            return cls(obj, all_attrs, str(id(obj)))


class ObjectConfigs(namedtuple("ObjectConfigs", "items all_attrs")):
    """Configuration for objects passed to resolver_factory."""

    @classmethod
    def from_configs(cls, configs: Iterable["ObjectConfig"]) -> "ObjectConfigs":
        all_attrs = set()
        configs = tuple(configs)
        for config in configs:
            all_attrs.update(config.all_attrs)
        return cls(configs, all_attrs)


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


def _search_callable_attr_is_property(attr, configs: ObjectConfigs) -> "WrapSearchResult | None":
    # if the attr is a property, we'll try to find the object that has the
    # property on the configs
    attr_name = attr.fget.__name__
    if attr_name not in configs.all_attrs:
        return None
    for obj, _all_attrs, resolver_id in configs.items:
        func = getattr(type(obj), attr_name, None)
        if func is not None and func is attr:
            return AttributeCallableSearchResult(attr_name, obj, resolver_id)
    return None


def _search_callable_attr_is_callable(attr, configs: ObjectConfigs) -> WrapSearchResult:
    # if the attr is an unbounded method, we'll try to find the bounded method
    # on the configs
    if not hasattr(attr, "__self__"):
        for obj, _all_attrs, resolver_id in configs.items:
            func = getattr(obj, attr.__name__, None)
            if func is not None and func.__func__ is attr:
                return CallableSearchResult(attr.__name__, func, resolver_id)

    return CallableSearchResult(attr, attr, None)


def _search_callable_in_configs(
    attr, configs: ObjectConfigs
) -> Generator[WrapSearchResult, None, None]:
    for obj, all_attrs, resolver_id in configs.items:
        if attr not in all_attrs:
            continue

        func = getattr(obj, attr)
        if not callable(func):
            yield AttributeCallableSearchResult(attr, obj, resolver_id)

        if getattr(func, "_is_sm_event", False):
            yield EventSearchResult(attr, func, resolver_id)

        yield CallableSearchResult(attr, func, resolver_id)


def search_callable(attr, configs: ObjectConfigs) -> Generator[WrapSearchResult, None, None]:  # noqa: C901
    if isinstance(attr, property):
        result = _search_callable_attr_is_property(attr, configs)
        if result is not None:
            yield result
        return

    if callable(attr):
        yield _search_callable_attr_is_callable(attr, configs)
        return

    if attr not in configs.all_attrs:
        return

    yield from _search_callable_in_configs(attr, configs)


def resolver_factory(objects: ObjectConfigs):
    """Factory that returns a configured resolver."""

    def resolver(attr) -> Generator[WrapSearchResult, None, None]:
        yield from search_callable(attr, objects)

    return resolver


def resolver_factory_from_objects(*objects: Tuple[Any, ...]):
    configs: ObjectConfigs = ObjectConfigs.from_configs(ObjectConfig.from_obj(o) for o in objects)
    return resolver_factory(configs)
