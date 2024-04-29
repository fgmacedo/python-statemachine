from bisect import insort
from collections import defaultdict
from collections import deque
from enum import IntEnum
from typing import Callable
from typing import Dict
from typing import Generator
from typing import List

from .exceptions import AttrNotFound
from .i18n import _
from .utils import ensure_iterable


class CallbackPriority(IntEnum):
    GENERIC = 0
    INLINE = 10
    DECORATOR = 20
    NAMING = 30
    AFTER = 40


def allways_true(*args, **kwargs):
    return True


class CallbackWrapper:
    def __init__(
        self,
        callback: Callable,
        condition: Callable,
        meta: "CallbackMeta",
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

    def __call__(self, *args, **kwargs):
        return self._callback(*args, **kwargs)


class CallbackMeta:
    """A thin wrapper that register info about actions and guards.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(
        self,
        func,
        suppress_errors=False,
        cond=None,
        priority: CallbackPriority = CallbackPriority.NAMING,
        expected_value=None,
    ):
        self.func = func
        self.suppress_errors = suppress_errors
        self.cond = cond
        self.expected_value = expected_value
        self.priority = priority

    def __repr__(self):
        return f"{type(self).__name__}({self.func!r}, suppress_errors={self.suppress_errors!r})"

    def __str__(self):
        return getattr(self.func, "__name__", self.func)

    def __eq__(self, other):
        return self.func == other.func

    def __hash__(self):
        return id(self)

    def _update_func(self, func):
        self.func = func

    def _wrap_callable(self, func, _expected_value):
        return func

    def build(self, resolver) -> Generator["CallbackWrapper", None, None]:
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        for callback in resolver(self.func):
            condition = next(resolver(self.cond)) if self.cond is not None else allways_true
            yield CallbackWrapper(
                callback=self._wrap_callable(callback, self.expected_value),
                condition=condition,
                meta=self,
                unique_key=callback.unique_key,
            )


class BoolCallbackMeta(CallbackMeta):
    """A thin wrapper that register info about actions and guards.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(
        self,
        func,
        suppress_errors=False,
        cond=None,
        priority: CallbackPriority = CallbackPriority.NAMING,
        expected_value=True,
    ):
        super().__init__(
            func, suppress_errors, cond, priority=priority, expected_value=expected_value
        )

    def __str__(self):
        name = super().__str__()
        return name if self.expected_value else f"!{name}"

    def _wrap_callable(self, func, expected_value):
        def bool_wrapper(*args, **kwargs):
            return bool(func(*args, **kwargs)) == expected_value

        return bool_wrapper


class CallbackMetaList:
    """List of `CallbackMeta` instances"""

    def __init__(self, factory=CallbackMeta):
        self.items: List[CallbackMeta] = []
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
        callback = self._add(func, **kwargs)
        if not getattr(func, "_callbacks_to_update", None):
            func._callbacks_to_update = set()
        func._callbacks_to_update.add(callback._update_func)
        func._is_event = is_event
        func._transitions = transitions

        return func

    def __call__(self, callback):
        """Allows usage of the callback list as a decorator."""
        return self._add_unbounded_callback(callback)

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def _add(self, func, **kwargs):
        meta = self.factory(func, **kwargs)

        if meta in self.items:
            return

        self.items.append(meta)
        return meta

    def add(self, callbacks, **kwargs):
        if callbacks is None:
            return self

        unprepared = ensure_iterable(callbacks)
        for func in unprepared:
            self._add(func, **kwargs)

        return self


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

    def _add(self, callback_meta: CallbackMeta, resolver: Callable):
        for callback in callback_meta.build(resolver):
            if callback.unique_key in self.items_already_seen:
                continue

            self.items_already_seen.add(callback.unique_key)
            insort(self.items, callback)

    def add(self, items: CallbackMetaList, resolver: Callable):
        """Validate configurations"""
        for item in items:
            self._add(item, resolver)
        return self

    def call(self, *args, **kwargs):
        return [
            callback(*args, **kwargs) for callback in self if callback.condition(*args, **kwargs)
        ]

    def all(self, *args, **kwargs):
        return all(condition(*args, **kwargs) for condition in self)


class CallbacksRegistry:
    def __init__(self) -> None:
        self._registry: Dict[CallbackMetaList, CallbacksExecutor] = defaultdict(CallbacksExecutor)

    def register(self, meta_list: CallbackMetaList, resolver):
        executor_list = self[meta_list]
        executor_list.add(meta_list, resolver)
        return executor_list

    def clear(self):
        self._registry.clear()

    def __getitem__(self, meta_list: CallbackMetaList) -> CallbacksExecutor:
        return self._registry[meta_list]

    def check(self, meta_list: CallbackMetaList):
        executor = self[meta_list]
        for meta in meta_list:
            if meta.suppress_errors:
                continue

            if any(callback for callback in executor if callback.meta == meta):
                continue
            raise AttrNotFound(
                _("Did not found name '{}' from model or statemachine").format(meta.func)
            )
