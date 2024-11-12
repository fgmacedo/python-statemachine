from dataclasses import dataclass
from functools import partial
from functools import reduce
from operator import attrgetter
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Iterable
from typing import List
from typing import Set
from typing import Tuple

from .callbacks import SPECS_ALL
from .callbacks import SpecReference
from .callbacks import allways_true
from .event import Event
from .exceptions import InvalidDefinition
from .i18n import _
from .signature import SignatureAdapter
from .spec_parser import custom_and
from .spec_parser import operator_mapping
from .spec_parser import parse_boolean_expr

if TYPE_CHECKING:
    from .callbacks import CallbackSpec
    from .callbacks import CallbackSpecList
    from .callbacks import CallbacksRegistry


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

    def build_key(self, attr_name) -> str:
        return f"{attr_name}@{self.resolver_id}"


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

    def resolve(
        self,
        specs: "CallbackSpecList",
        registry: "CallbacksRegistry",
        allowed_references: SpecReference = SPECS_ALL,
    ):
        found_convention_specs = specs.conventional_specs & self.all_attrs

        for spec in specs:
            if (spec.reference not in allowed_references) or (
                spec.is_convention and spec.func not in found_convention_specs
            ):
                continue

            executor = registry[specs.grouper(spec.group).key]
            for key, builder in self.build(spec):
                executor.add(key, spec, builder)

    def _take_callback(self, name: str, names_not_found_handler: Callable) -> Callable:
        callbacks: List[Callable] = []
        for key, builder in self.search_name(name):
            callback = builder()
            callback.unique_key = key  # type: ignore[attr-defined]
            callbacks.append(callback)

        if len(callbacks) == 0:
            names_not_found_handler(name)
            return allways_true
        elif len(callbacks) == 1:
            return callbacks[0]
        else:
            return reduce(custom_and, callbacks)

    def build(self, spec: "CallbackSpec"):
        """
        Resolves the `spec` into callables in the `registry`.

        Args:
            spec (CallbackSpec): A spec to be resolved.
            registry (callable): A callable that will be used to store the resolved callables.
        """
        if not spec.may_contain_boolean_expression:
            yield from self.search(spec)
            return

        # Resolves boolean expressions

        names_not_found: Set[str] = set()
        take_callback_partial = partial(
            self._take_callback, names_not_found_handler=names_not_found.add
        )

        try:
            expression = parse_boolean_expr(spec.func, take_callback_partial, operator_mapping)
        except SyntaxError as err:
            raise InvalidDefinition(
                _("Failed to parse boolean expression '{}'").format(spec.func)
            ) from err
        if not expression or names_not_found:
            spec.names_not_found = names_not_found
            return

        yield expression.unique_key, lambda: expression

    def search(self, spec: "CallbackSpec"):
        if spec.reference is SpecReference.NAME:
            yield from self.search_name(spec.attr_name)
        elif spec.reference is SpecReference.CALLABLE:
            yield from self._search_callable(spec)
        elif spec.reference is SpecReference.PROPERTY:
            yield from self._search_property(spec)
        else:  # never reached here from tests but put an exception for safety. pragma: no cover
            raise ValueError(f"Invalid reference {spec.reference}")

    def _search_property(self, spec):
        # if the attr is a property, we'll try to find the object that has the
        # property on the configs
        attr_name = spec.attr_name
        if attr_name not in self.all_attrs:
            return
        for listener in self.items:
            func = getattr(type(listener.obj), attr_name, None)
            if func is not None and func is spec.func:
                yield (
                    listener.build_key(attr_name),
                    partial(attr_method, attr_name, listener.obj),
                )
                return

    def _search_callable(self, spec):
        # if the attr is an unbounded method, we'll try to find the bounded method
        # on the self
        if not spec.is_bounded:
            for listener in self.items:
                func = getattr(listener.obj, spec.attr_name, None)
                if func is not None and func.__func__ is spec.func:
                    yield listener.build_key(spec.attr_name), partial(callable_method, func)
                    return

        yield f"{spec.attr_name}@None", partial(callable_method, spec.func)

    def search_name(self, name):
        for listener in self.items:
            if name not in listener.all_attrs:
                continue

            key = listener.build_key(name)
            func = getattr(listener.obj, name)
            if not callable(func):
                yield key, partial(attr_method, name, listener.obj)
                continue

            if isinstance(func, Event):
                yield key, partial(event_method, func)
                continue

            yield key, partial(callable_method, func)


def callable_method(a_callable) -> Callable:
    sig = SignatureAdapter.from_callable(a_callable)
    sig_bind_expected = sig.bind_expected

    metadata_to_copy = a_callable.func if isinstance(a_callable, partial) else a_callable

    if sig.is_coroutine:

        async def signature_adapter(*args: Any, **kwargs: Any) -> Any:
            ba = sig_bind_expected(*args, **kwargs)
            return await a_callable(*ba.args, **ba.kwargs)
    else:

        def signature_adapter(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
            ba = sig_bind_expected(*args, **kwargs)
            return a_callable(*ba.args, **ba.kwargs)

    signature_adapter.__name__ = metadata_to_copy.__name__
    signature_adapter.__doc__ = metadata_to_copy.__doc__
    signature_adapter.is_coroutine = sig.is_coroutine  # type: ignore[attr-defined]

    return signature_adapter


def attr_method(attribute, obj) -> Callable:
    getter = attrgetter(attribute)

    def method(*args, **kwargs):
        return getter(obj)

    method.__name__ = attribute
    return method


def event_method(func) -> Callable:
    def method(*args, **kwargs):
        kwargs.pop("machine", None)
        return func(*args, **kwargs)

    return method


def resolver_factory_from_objects(*objects: Tuple[Any, ...]):
    return Listeners.from_listeners(Listener.from_obj(o) for o in objects)
