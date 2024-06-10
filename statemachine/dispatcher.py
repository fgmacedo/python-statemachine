from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import Any
from typing import Generator
from typing import Iterable
from typing import Set
from typing import Tuple

from statemachine.callbacks import SpecReference

from .signature import SignatureAdapter

if TYPE_CHECKING:
    from .callbacks import CallbacksExecutor
    from .callbacks import CallbackSpec
    from .callbacks import CallbackSpecList


@dataclass
class ObjectConfig:
    """Configuration for objects passed to resolver_factory.

    Args:
        obj: Any object that will serve as lookup for attributes.
        skip_attrs: Protected attrs that will be ignored on the search.
    """

    obj: object
    all_attrs: Set[str]
    resolver_id: str

    @classmethod
    def from_obj(cls, obj, skip_attrs=None) -> "ObjectConfig":
        if isinstance(obj, ObjectConfig):
            return obj
        else:
            if skip_attrs is None:
                skip_attrs = set()
            all_attrs = set(dir(obj)) - skip_attrs
            return cls(obj, all_attrs, str(id(obj)))


@dataclass
class ObjectConfigs:
    """Configuration for objects passed to resolver_factory."""

    items: Tuple[ObjectConfig, ...]
    all_attrs: Set[str]

    @classmethod
    def from_configs(cls, configs: Iterable["ObjectConfig"]) -> "ObjectConfigs":
        configs = tuple(configs)
        all_attrs = set().union(*(config.all_attrs for config in configs))
        return cls(configs, all_attrs)

    def resolve(self, specs: "CallbackSpecList", callbacks: "CallbacksExecutor"):
        convention_specs = {spec.func for spec in specs if spec.is_convention}
        found_convention_specs = convention_specs & self.all_attrs
        filtered_specs = [
            spec for spec in specs if not spec.is_convention or spec.func in found_convention_specs
        ]
        if not filtered_specs:
            return

        callbacks.add(filtered_specs, self)

    def __call__(self, attr) -> Generator["WrapSearchResult", None, None]:
        yield from search_callable(attr, self)

    def search(self, spec: "CallbackSpec") -> Generator["WrapSearchResult", None, None]:
        if spec.reference is SpecReference.NAME:
            yield from self._search_name(spec.func)
            return
        elif spec.reference is SpecReference.CALLABLE:
            yield self._search_callable(spec)
            return
        elif spec.reference is SpecReference.PROPERTY:
            result = self._search_property(spec)
            if result is not None:
                yield result
            return
        else:
            raise ValueError(f"Invalid reference {spec.reference}")

    def _search_property(self, spec) -> "WrapSearchResult | None":
        # if the attr is a property, we'll try to find the object that has the
        # property on the configs
        attr_name = spec.attr_name
        if attr_name not in self.all_attrs:
            return None
        for config in self.items:
            func = getattr(type(config.obj), attr_name, None)
            if func is not None and func is spec.func:
                return AttributeCallableSearchResult(attr_name, config.obj, config.resolver_id)
        return None

    def _search_callable(self, spec) -> "WrapSearchResult":
        # if the attr is an unbounded method, we'll try to find the bounded method
        # on the self
        if not spec.is_bounded:
            for config in self.items:
                func = getattr(config.obj, spec.attr_name, None)
                if func is not None and func.__func__ is spec.func:
                    return CallableSearchResult(spec.attr_name, func, config.resolver_id)

        return CallableSearchResult(spec.func, spec.func, None)

    def _search_name(self, name) -> Generator["WrapSearchResult", None, None]:
        for config in self.items:
            if name not in config.all_attrs:
                continue

            func = getattr(config.obj, name)
            if not callable(func):
                yield AttributeCallableSearchResult(name, config.obj, config.resolver_id)

            if getattr(func, "_is_sm_event", False):
                yield EventSearchResult(name, func, config.resolver_id)

            yield CallableSearchResult(name, func, config.resolver_id)


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


def _search_property(attr, configs: ObjectConfigs) -> "WrapSearchResult | None":
    # if the attr is a property, we'll try to find the object that has the
    # property on the configs
    attr_name = attr.fget.__name__
    if attr_name not in configs.all_attrs:
        return None
    for config in configs.items:
        func = getattr(type(config.obj), attr_name, None)
        if func is not None and func is attr:
            return AttributeCallableSearchResult(attr_name, config.obj, config.resolver_id)
    return None


def _search_callable(attr, configs: ObjectConfigs) -> WrapSearchResult:
    # if the attr is an unbounded method, we'll try to find the bounded method
    # on the configs
    if not hasattr(attr, "__self__"):
        for config in configs.items:
            func = getattr(config.obj, attr.__name__, None)
            if func is not None and func.__func__ is attr:
                return CallableSearchResult(attr.__name__, func, config.resolver_id)

    return CallableSearchResult(attr, attr, None)


def _search_name(name, configs: ObjectConfigs) -> Generator[WrapSearchResult, None, None]:
    for config in configs.items:
        if name not in config.all_attrs:
            continue

        func = getattr(config.obj, name)
        if not callable(func):
            yield AttributeCallableSearchResult(name, config.obj, config.resolver_id)

        if getattr(func, "_is_sm_event", False):
            yield EventSearchResult(name, func, config.resolver_id)

        yield CallableSearchResult(name, func, config.resolver_id)


def search_callable(attr, configs: ObjectConfigs) -> Generator[WrapSearchResult, None, None]:  # noqa: C901
    if isinstance(attr, property):
        result = _search_property(attr, configs)
        if result is not None:
            yield result
        return

    if callable(attr):
        yield _search_callable(attr, configs)
        return

    if attr not in configs.all_attrs:
        return

    yield from _search_name(attr, configs)


def resolver_factory_from_objects(*objects: Tuple[Any, ...]):
    return ObjectConfigs.from_configs(ObjectConfig.from_obj(o) for o in objects)
