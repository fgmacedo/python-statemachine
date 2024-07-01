from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Generator
from typing import Iterable
from typing import Set
from typing import Tuple

from statemachine.callbacks import SpecReference

from .signature import SignatureAdapter

if TYPE_CHECKING:
    from .callbacks import CallbackSpec
    from .callbacks import CallbackSpecList


@dataclass
class Listener:
    """Object reference that provides attributes to be used as callbacks.

    Args:
        obj: Any object that will serve as lookup for attributes.
        skip_attrs: Protected attrs that will be ignored on the search.
    """

    obj: object
    all_attrs: Set[str]
    resolver_id: str

    @classmethod
    def from_obj(cls, obj, skip_attrs=None) -> "Listener":
        if isinstance(obj, Listener):
            return obj
        else:
            if skip_attrs is None:
                skip_attrs = set()
            all_attrs = set(dir(obj)) - skip_attrs
            return cls(obj, all_attrs, str(id(obj)))


@dataclass
class Listeners:
    """Listeners that provides attributes to be used as callbacks."""

    items: Tuple[Listener, ...]
    all_attrs: Set[str]

    @classmethod
    def from_listeners(cls, listeners: Iterable["Listener"]) -> "Listeners":
        listeners = tuple(listeners)
        all_attrs = set().union(*(listener.all_attrs for listener in listeners))
        return cls(listeners, all_attrs)

    def resolve(self, specs: "CallbackSpecList", registry):
        found_convention_specs = specs.conventional_specs & self.all_attrs
        filtered_specs = [
            spec for spec in specs if not spec.is_convention or spec.func in found_convention_specs
        ]
        if not filtered_specs:
            return

        for spec in filtered_specs:
            registry[spec.group.build_key(specs)]._add(spec, self)

    def search(self, spec: "CallbackSpec") -> Generator["Callable", None, None]:
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
        else:  # never reached here from tests but put an exception for safety. pragma: no cover
            raise ValueError(f"Invalid reference {spec.reference}")

    def _search_property(self, spec) -> "Callable | None":
        # if the attr is a property, we'll try to find the object that has the
        # property on the configs
        attr_name = spec.attr_name
        if attr_name not in self.all_attrs:
            return None
        for config in self.items:
            func = getattr(type(config.obj), attr_name, None)
            if func is not None and func is spec.func:
                return attr_method(attr_name, config.obj, config.resolver_id)
        return None

    def _search_callable(self, spec) -> "Callable":
        # if the attr is an unbounded method, we'll try to find the bounded method
        # on the self
        if not spec.is_bounded:
            for config in self.items:
                func = getattr(config.obj, spec.attr_name, None)
                if func is not None and func.__func__ is spec.func:
                    return callable_method(spec.attr_name, func, config.resolver_id)

        return callable_method(spec.func, spec.func, None)

    def _search_name(self, name) -> Generator["Callable", None, None]:
        for config in self.items:
            if name not in config.all_attrs:
                continue

            func = getattr(config.obj, name)
            if not callable(func):
                yield attr_method(name, config.obj, config.resolver_id)
                continue

            if getattr(func, "_is_sm_event", False):
                yield event_method(name, func, config.resolver_id)
                continue

            yield callable_method(name, func, config.resolver_id)


def callable_method(attribute, a_callable, resolver_id) -> Callable:
    method = SignatureAdapter.wrap(a_callable)
    method.unique_key = f"{attribute}@{resolver_id}"  # type: ignore[attr-defined]
    method.__name__ = a_callable.__name__
    method.__doc__ = a_callable.__doc__
    return method


def attr_method(attribute, obj, resolver_id) -> Callable:
    getter = attrgetter(attribute)

    def method(*args, **kwargs):
        return getter(obj)

    method.unique_key = f"{attribute}@{resolver_id}"  # type: ignore[attr-defined]
    return method


def event_method(attribute, func, resolver_id) -> Callable:
    def method(*args, **kwargs):
        kwargs.pop("machine", None)
        return func(*args, **kwargs)

    method.unique_key = f"{attribute}@{resolver_id}"  # type: ignore[attr-defined]
    return method


def resolver_factory_from_objects(*objects: Tuple[Any, ...]):
    return Listeners.from_listeners(Listener.from_obj(o) for o in objects)
