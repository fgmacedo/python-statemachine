import asyncio
from bisect import insort
from collections import defaultdict
from collections import deque
from enum import IntEnum
from enum import IntFlag
from enum import auto
from functools import partial
from functools import reduce
from inspect import isawaitable
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING
from typing import Callable
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import List
from typing import Set
from typing import Type

from .exceptions import AttrNotFound
from .exceptions import InvalidDefinition
from .i18n import _
from .spec_parser import custom_and
from .spec_parser import operator_mapping
from .spec_parser import parse_boolean_expr
from .utils import ensure_iterable

if TYPE_CHECKING:
    from statemachine.dispatcher import Listeners


class CallbackPriority(IntEnum):
    GENERIC = 0
    INLINE = 10
    DECORATOR = 20
    NAMING = 30
    AFTER = 40


class SpecReference(IntFlag):
    NAME = auto()
    CALLABLE = auto()
    PROPERTY = auto()


SPECS_ALL = SpecReference.NAME | SpecReference.CALLABLE | SpecReference.PROPERTY
SPECS_SAFE = SpecReference.NAME


class CallbackGroup(IntEnum):
    ENTER = auto()
    EXIT = auto()
    VALIDATOR = auto()
    BEFORE = auto()
    ON = auto()
    AFTER = auto()
    COND = auto()

    def build_key(self, specs: "CallbackSpecList") -> str:
        return f"{self.name}@{id(specs)}"


def allways_true(*args, **kwargs):
    return True


def take_callback(name: str, resolver: "Listeners", not_found_handler: Callable) -> Callable:
    callbacks = list(resolver.search_name(name))
    if len(callbacks) == 0:
        not_found_handler(name)
        return allways_true
    elif len(callbacks) == 1:
        return callbacks[0]
    else:
        return reduce(custom_and, callbacks)


class CallbackSpec:
    """Specs about callbacks.

    At first, `func` can be a name (string), a property or a callable.

    Names, properties and unbounded callables should be resolved to a callable
    before any real call is performed.
    """

    def __init__(
        self,
        func,
        group: CallbackGroup,
        is_convention=False,
        cond=None,
        priority: CallbackPriority = CallbackPriority.NAMING,
        expected_value=None,
    ):
        self.func = func
        self.group = group
        self.is_convention = is_convention
        self.cond = cond
        self.expected_value = expected_value
        self.priority = priority

        if isinstance(func, property):
            self.reference = SpecReference.PROPERTY
            self.attr_name: str = func and func.fget and func.fget.__name__ or ""
        elif callable(func):
            self.reference = SpecReference.CALLABLE
            self.is_bounded = hasattr(func, "__self__")
            self.attr_name = func.__name__
        else:
            self.reference = SpecReference.NAME
            self.attr_name = func

    def __repr__(self):
        return f"{type(self).__name__}({self.func!r}, is_convention={self.is_convention!r})"

    def __str__(self):
        name = getattr(self.func, "__name__", self.func)
        if self.expected_value is False:
            name = f"!{name}"
        return name

    def __eq__(self, other):
        return self.func == other.func and self.group == other.group

    def __hash__(self):
        return id(self)

    def _update_func(self, func: Callable, attr_name: str):
        self.func = func
        self.reference = SpecReference.CALLABLE
        self.attr_name = attr_name

    def _wrap(self, callback):
        condition = self.cond if self.cond is not None else allways_true
        return CallbackWrapper(
            callback=callback,
            condition=condition,
            meta=self,
            unique_key=callback.unique_key,
        )

    def build(self, resolver: "Listeners") -> Generator["CallbackWrapper", None, None]:
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        if (
            not self.is_convention
            and self.group == CallbackGroup.COND
            and self.reference == SpecReference.NAME
        ):
            names_not_found: Set[str] = set()
            take_callback_partial = partial(
                take_callback, resolver=resolver, not_found_handler=names_not_found.add
            )
            try:
                expression = parse_boolean_expr(self.func, take_callback_partial, operator_mapping)
            except SyntaxError as err:
                raise InvalidDefinition(
                    _("Failed to parse boolean expression '{}'").format(self.func)
                ) from err
            if not expression or names_not_found:
                self.names_not_found = names_not_found
                return
            yield self._wrap(expression)
            return

        for callback in resolver.search(self):
            yield self._wrap(callback)


class SpecListGrouper:
    def __init__(
        self, list: "CallbackSpecList", group: CallbackGroup, factory=CallbackSpec
    ) -> None:
        self.list = list
        self.group = group
        self.factory = factory
        self.key = group.build_key(list)

    def add(self, callbacks, **kwargs):
        self.list.add(callbacks, group=self.group, factory=self.factory, **kwargs)
        return self

    def __call__(self, callback):
        return self.list._add_unbounded_callback(callback, group=self.group, factory=self.factory)

    def _add_unbounded_callback(self, func, is_event=False, transitions=None, **kwargs):
        self.list._add_unbounded_callback(
            func,
            is_event=is_event,
            transitions=transitions,
            group=self.group,
            factory=self.factory,
            **kwargs,
        )

    def __iter__(self):
        return (item for item in self.list if item.group == self.group)


class CallbackSpecList:
    """List of {ref}`CallbackSpec` instances"""

    def __init__(self, factory=CallbackSpec):
        self.items: List[CallbackSpec] = []
        self.conventional_specs = set()
        self.factory = factory

    def __repr__(self):
        return f"{type(self).__name__}({self.items!r}, factory={self.factory!r})"

    def _add_unbounded_callback(self, func, is_event=False, transitions=None, **kwargs):
        """This list was a target for adding a func using decorator
        `@<state|event>[.on|before|after|enter|exit]` syntax.

        If we assign ``func`` directly as callable on the ``items`` list,
        this will result in an `unbounded method error`, with `func` expecting a parameter
        ``self`` not defined.

        The implemented solution is to resolve the collision giving the func a reference method.
        To update It's callback when the name is resolved on the
        :func:`StateMachineMetaclass.add_from_attributes`.
        If the ``func`` is bounded It will be used directly, if not, it's ref will be replaced
        by the given attr name and on `statemachine._setup()` the dynamic name will be resolved
        properly.

        Args:
            func (callable): The decorated method to add on the transitions occurs.
            is_event (bool): If the func is also an event, we'll create a trigger and link the
                event name to the transitions.
            transitions (TransitionList): If ``is_event``, the transitions to be attached to the
                event.

        """
        spec = self._add(func, **kwargs)
        if not getattr(func, "_specs_to_update", None):
            func._specs_to_update = set()
        if is_event:
            func._specs_to_update.add(spec._update_func)
        func._transitions = transitions

        return func

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def grouper(
        self, group: CallbackGroup, factory: Type[CallbackSpec] = CallbackSpec
    ) -> SpecListGrouper:
        return SpecListGrouper(self, group, factory=factory)

    def _add(self, func, group: CallbackGroup, factory=None, **kwargs):
        if factory is None:
            factory = self.factory
        spec = factory(func, group, **kwargs)

        if spec in self.items:
            return

        self.items.append(spec)
        if spec.is_convention:
            self.conventional_specs.add(spec.func)
        return spec

    def add(self, callbacks, group: CallbackGroup, **kwargs):
        if callbacks is None:
            return self

        unprepared = ensure_iterable(callbacks)
        for func in unprepared:
            self._add(func, group=group, **kwargs)

        return self


class CallbackWrapper:
    def __init__(
        self,
        callback: Callable,
        condition: Callable,
        meta: "CallbackSpec",
        unique_key: str,
    ) -> None:
        self._callback = callback
        self._iscoro = iscoroutinefunction(callback)
        self.condition = condition
        self.meta = meta
        self.unique_key = unique_key
        self.expected_value = self.meta.expected_value

    def __repr__(self):
        return f"{type(self).__name__}({self.unique_key})"

    def __str__(self):
        return str(self.meta)

    def __lt__(self, other):
        return self.meta.priority < other.meta.priority

    async def __call__(self, *args, **kwargs):
        value = self._callback(*args, **kwargs)
        if isawaitable(value):
            value = await value

        if self.expected_value is not None:
            return bool(value) == self.expected_value
        return value

    def call(self, *args, **kwargs):
        value = self._callback(*args, **kwargs)
        if self.expected_value is not None:
            return bool(value) == self.expected_value
        return value


class CallbacksExecutor:
    """A list of callbacks that can be executed in order."""

    def __init__(self):
        self.items: List[CallbackWrapper] = deque()
        self.items_already_seen = set()

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        return f"{type(self).__name__}({self.items!r})"

    def __str__(self):
        return ", ".join(str(c) for c in self)

    def _add(self, spec: CallbackSpec, resolver: "Listeners"):
        for callback in spec.build(resolver):
            if callback.unique_key in self.items_already_seen:
                continue

            self.items_already_seen.add(callback.unique_key)
            insort(self.items, callback)

    def add(self, items: Iterable[CallbackSpec], resolver: "Listeners"):
        """Validate configurations"""
        for item in items:
            self._add(item, resolver)
        return self

    async def async_call(self, *args, **kwargs):
        return await asyncio.gather(
            *(
                callback(*args, **kwargs)
                for callback in self
                if callback.condition(*args, **kwargs)
            )
        )

    async def async_all(self, *args, **kwargs):
        coros = [condition(*args, **kwargs) for condition in self]
        for coro in asyncio.as_completed(coros):
            if not await coro:
                return False
        return True

    def call(self, *args, **kwargs):
        return [
            callback.call(*args, **kwargs)
            for callback in self
            if callback.condition(*args, **kwargs)
        ]

    def all(self, *args, **kwargs):
        for condition in self:
            if not condition.call(*args, **kwargs):
                return False
        return True


class CallbacksRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, CallbacksExecutor] = defaultdict(CallbacksExecutor)
        self.has_async_callbacks: bool = False

    def clear(self):
        self._registry.clear()

    def __getitem__(self, key: str) -> CallbacksExecutor:
        return self._registry[key]

    def check(self, specs: CallbackSpecList):
        for meta in specs:
            if meta.is_convention:
                continue

            if any(
                callback for callback in self[meta.group.build_key(specs)] if callback.meta == meta
            ):
                continue
            if hasattr(meta, "names_not_found"):
                raise AttrNotFound(
                    _("Did not found name '{}' from model or statemachine").format(
                        ", ".join(meta.names_not_found)
                    ),
                )
            raise AttrNotFound(
                _("Did not found name '{}' from model or statemachine").format(meta.func)
            )

    def async_or_sync(self):
        self.has_async_callbacks = any(
            callback._iscoro for executor in self._registry.values() for callback in executor
        )
