from bisect import insort
from collections import defaultdict
from collections import deque
from enum import IntEnum
from enum import auto
from typing import Callable
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import List
from typing import Type

from .exceptions import AttrNotFound
from .i18n import _
from .utils import ensure_iterable


class CallbackPriority(IntEnum):
    GENERIC = 0
    INLINE = 10
    DECORATOR = 20
    NAMING = 30
    AFTER = 40


class SpecReference(IntEnum):
    NAME = 1
    CALLABLE = 2
    PROPERTY = 3


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


async def allways_true(*args, **kwargs):
    return True


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
        return getattr(self.func, "__name__", self.func)

    def __eq__(self, other):
        return self.func == other.func and self.group == other.group

    def __hash__(self):
        return id(self)

    def _update_func(self, func: Callable, attr_name: str):
        self.func = func
        self.reference = SpecReference.CALLABLE
        self.attr_name = attr_name

    def _wrap_callable(self, func, _expected_value):
        return func

    def build(self, resolver) -> Generator["CallbackWrapper", None, None]:
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        for callback in resolver.search(self):
            condition = (
                next(resolver.search(CallbackSpec(self.cond, CallbackGroup.COND)))
                if self.cond is not None
                else allways_true
            )
            yield CallbackWrapper(
                callback=self._wrap_callable(callback, self.expected_value),
                condition=condition,
                meta=self,
                unique_key=callback.unique_key,
            )


class BoolCallbackSpec(CallbackSpec):
    """A thin wrapper that register info about actions and guards.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(
        self,
        func,
        group: CallbackGroup,
        is_convention=False,
        cond=None,
        priority: CallbackPriority = CallbackPriority.NAMING,
        expected_value=True,
    ):
        super().__init__(
            func, group, is_convention, cond, priority=priority, expected_value=expected_value
        )

    def __str__(self):
        name = super().__str__()
        return name if self.expected_value else f"!{name}"

    def _wrap_callable(self, func, expected_value):
        async def bool_wrapper(*args, **kwargs):
            return bool(await func(*args, **kwargs)) == expected_value

        return bool_wrapper


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

    def __str__(self):
        return ", ".join(str(c) for c in self)


class CallbackSpecList:
    """List of {ref}`CallbackSpec` instances"""

    def __init__(self, factory=CallbackSpec):
        self.items: List[CallbackSpec] = []
        self.conventional_specs = set()
        self.factory = factory

    def __repr__(self):
        return f"{type(self).__name__}({self.items!r}, factory={self.factory!r})"

    def __str__(self):
        return ", ".join(str(c) for c in self)

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
        func._is_event = is_event
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
        self.condition = condition
        self.meta = meta
        self.unique_key = unique_key

    def __repr__(self):
        return f"{type(self).__name__}({self.unique_key})"

    def __str__(self):
        return str(self.meta)

    def __lt__(self, other):
        return self.meta.priority < other.meta.priority

    async def __call__(self, *args, **kwargs):
        return await self._callback(*args, **kwargs)


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

    def _add(self, spec: CallbackSpec, resolver: Callable):
        for callback in spec.build(resolver):
            if callback.unique_key in self.items_already_seen:
                continue

            self.items_already_seen.add(callback.unique_key)
            insort(self.items, callback)

    def add(self, items: Iterable[CallbackSpec], resolver: Callable):
        """Validate configurations"""
        for item in items:
            self._add(item, resolver)
        return self

    async def call(self, *args, **kwargs):
        return [
            await callback(*args, **kwargs)
            for callback in self
            if await callback.condition(*args, **kwargs)
        ]

    async def all(self, *args, **kwargs):
        for condition in self:
            if not await condition(*args, **kwargs):
                return False
        return True


class CallbacksRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, CallbacksExecutor] = defaultdict(CallbacksExecutor)

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
            raise AttrNotFound(
                _("Did not found name '{}' from model or statemachine").format(meta.func)
            )
