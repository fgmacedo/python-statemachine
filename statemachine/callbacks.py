import asyncio
from bisect import insort
from collections import defaultdict
from collections import deque
from enum import IntEnum
from enum import IntFlag
from enum import auto
from inspect import isawaitable
from typing import TYPE_CHECKING
from typing import Callable
from typing import Dict
from typing import List

from .exceptions import AttrNotFound
from .i18n import _
from .utils import ensure_iterable

if TYPE_CHECKING:
    from typing import Set


def allways_true(*args, **kwargs):
    return True


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


class CallbackSpec:
    """Specs about callbacks.

    At first, `func` can be a name (string), a property or a callable.

    Names, properties and unbounded callables should be resolved to a callable
    before any real call is performed.
    """

    names_not_found: "Set[str] | None" = None
    """List of names that were not found on the model or statemachine"""

    def __init__(
        self,
        func,
        group: CallbackGroup,
        is_convention=False,
        is_event: bool = False,
        cond=None,
        priority: CallbackPriority = CallbackPriority.NAMING,
        expected_value=None,
    ):
        self.func = func
        self.group = group
        self.is_convention = is_convention
        self.is_event = is_event
        self.cond = cond
        self.expected_value = expected_value
        self.priority = priority

        if isinstance(func, property):
            self.reference = SpecReference.PROPERTY
            self.attr_name: str = func and func.fget and func.fget.__name__ or ""
        elif callable(func):
            self.reference = SpecReference.CALLABLE
            self.is_bounded = hasattr(func, "__self__")
            self.attr_name = (
                func.__name__ if not self.is_event or self.is_bounded else f"_{func.__name__}_"
            )
            if not self.is_bounded:
                func.attr_name = self.attr_name
                func.is_event = is_event
        else:
            self.reference = SpecReference.NAME
            self.attr_name = func

        self.may_contain_boolean_expression = (
            not self.is_convention
            and self.group == CallbackGroup.COND
            and self.reference == SpecReference.NAME
        )

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


class SpecListGrouper:
    def __init__(self, list: "CallbackSpecList", group: CallbackGroup) -> None:
        self.list = list
        self.group = group
        self.key = group.build_key(list)

    def add(self, callbacks, **kwargs):
        self.list.add(callbacks, group=self.group, **kwargs)
        return self

    def __call__(self, callback):
        return self.list._add_unbounded_callback(callback, group=self.group)

    def _add_unbounded_callback(self, func, is_event=False, transitions=None, **kwargs):
        self.list._add_unbounded_callback(
            func,
            is_event=is_event,
            transitions=transitions,
            group=self.group,
            **kwargs,
        )

    def __iter__(self):
        return (item for item in self.list if item.group == self.group)


class CallbackSpecList:
    """List of {ref}`CallbackSpec` instances"""

    def __init__(self, factory=CallbackSpec):
        self.items: List[CallbackSpec] = []
        self.conventional_specs = set()
        self._groupers: Dict[CallbackGroup, SpecListGrouper] = {}
        self.factory = factory

    def __repr__(self):
        return f"{type(self).__name__}({self.items!r}, factory={self.factory!r})"

    def _add_unbounded_callback(self, func, transitions=None, **kwargs):
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
        self._add(func, **kwargs)
        func._transitions = transitions

        return func

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def grouper(self, group: CallbackGroup) -> SpecListGrouper:
        if group not in self._groupers:
            self._groupers[group] = SpecListGrouper(self, group)
        return self._groupers[group]

    def _add(self, func, group: CallbackGroup, **kwargs):
        if isinstance(func, CallbackSpec):
            spec = func
        else:
            spec = self.factory(func, group, **kwargs)

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
        self._iscoro = getattr(callback, "is_coroutine", False)
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

    def add(self, key: str, spec: CallbackSpec, builder: Callable[[], Callable]):
        if key in self.items_already_seen:
            return

        self.items_already_seen.add(key)

        condition = spec.cond if spec.cond is not None else allways_true
        wrapper = CallbackWrapper(
            callback=builder(),
            condition=condition,
            meta=spec,
            unique_key=key,
        )

        insort(self.items, wrapper)

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

            if meta.names_not_found:
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

    def call(self, key: str, *args, **kwargs):
        if key not in self._registry:
            return []
        return self._registry[key].call(*args, **kwargs)

    def async_call(self, key: str, *args, **kwargs):
        return self._registry[key].async_call(*args, **kwargs)

    def all(self, key: str, *args, **kwargs):
        if key not in self._registry:
            return True
        return self._registry[key].all(*args, **kwargs)

    def async_all(self, key: str, *args, **kwargs):
        return self._registry[key].async_all(*args, **kwargs)

    def str(self, key: str) -> str:
        if key not in self._registry:
            return ""
        return str(self._registry[key])
