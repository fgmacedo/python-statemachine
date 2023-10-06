from collections import defaultdict
from collections import deque
from typing import Callable
from typing import Dict
from typing import List

from .exceptions import AttrNotFound
from .i18n import _
from .utils import ensure_iterable


class CallbackWrapper:
    def __init__(
        self,
        callback: Callable,
        condition: Callable,
        unique_key: str,
        expected_value: "bool | None" = None,
    ) -> None:
        self._callback = callback
        self.condition = condition
        self.unique_key = unique_key
        self.expected_value = expected_value

    def __repr__(self):
        return f"{type(self).__name__}({self.unique_key})"

    def __call__(self, *args, **kwargs):
        result = self._callback(*args, **kwargs)
        if self.expected_value is not None:
            return bool(result) == self.expected_value
        return result


class CallbackMeta:
    """A thin wrapper that register info about actions and guards.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(self, func, suppress_errors=False, cond=None, expected_value=None):
        self.func = func
        self.suppress_errors = suppress_errors
        self.cond = CallbackMetaList().add(cond)
        self.expected_value = expected_value

    def __repr__(self):
        return f"{type(self).__name__}({self.func!r})"

    def __str__(self):
        return getattr(self.func, "__name__", self.func)

    def __eq__(self, other):
        return self.func == other.func

    def __hash__(self):
        return id(self)

    def _update_func(self, func):
        self.func = func

    def build(self, resolver) -> "CallbackWrapper | None":
        """
        Resolves the `func` into a usable callable.

        Args:
            resolver (callable): A method responsible to build and return a valid callable that
                can receive arbitrary parameters like `*args, **kwargs`.
        """
        callback = resolver(self.func)
        if not callback.is_empty:
            conditions = CallbacksExecutor()
            conditions.add(self.cond, resolver)

            return CallbackWrapper(
                callback=callback,
                condition=conditions.all,
                unique_key=callback.unique_key,
                expected_value=self.expected_value,
            )

        if not self.suppress_errors:
            raise AttrNotFound(
                _("Did not found name '{}' from model or statemachine").format(
                    self.func
                )
            )
        return None


class BoolCallbackMeta(CallbackMeta):
    """A thin wrapper that register info about actions and guards.

    At first, `func` can be a string or a callable, and even if it's already
    a callable, his signature can mismatch.

    After instantiation, `.setup(resolver)` must be called before any real
    call is performed, to allow the proper callback resolution.
    """

    def __init__(self, func, suppress_errors=False, cond=None, expected_value=True):
        self.func = func
        self.suppress_errors = suppress_errors
        self.cond = CallbackMetaList().add(cond)
        self.expected_value = expected_value

    def __str__(self):
        name = super().__str__()
        return name if self.expected_value else f"!{name}"


class CallbackMetaList:
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
        return self._add_unbounded_callback(callback)

    def __iter__(self):
        return iter(self.items)

    def clear(self):
        self.items = []

    def _add(self, func, registry=None, prepend=False, **kwargs):
        meta = self.factory(func, **kwargs)
        if registry is not None and not registry(self, meta, prepend=prepend):
            return

        if meta in self.items:
            return

        if prepend:
            self.items.insert(0, meta)
        else:
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
    def __init__(self):
        self.items: List[CallbackWrapper] = deque()
        self.items_already_seen = set()

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        return f"{type(self).__name__}({self.items!r})"

    def add_one(
        self, callback_info: CallbackMeta, resolver: Callable, prepend: bool = False
    ) -> "CallbackWrapper | None":
        callback = callback_info.build(resolver)
        if callback is None:
            return None

        if callback.unique_key in self.items_already_seen:
            return None

        self.items_already_seen.add(callback.unique_key)
        if prepend:
            self.items.insert(0, callback)
        else:
            self.items.append(callback)
        return callback

    def add(self, items: CallbackMetaList, resolver: Callable):
        """Validate configurations"""
        for item in items:
            self.add_one(item, resolver)
        return self

    def call(self, *args, **kwargs):
        return [
            callback(*args, **kwargs)
            for callback in self
            if callback.condition(*args, **kwargs)
        ]

    def all(self, *args, **kwargs):
        return all(condition(*args, **kwargs) for condition in self)


class CallbacksRegistry:
    def __init__(self) -> None:
        self._registry: Dict[CallbackMetaList, CallbacksExecutor] = defaultdict(
            CallbacksExecutor
        )

    def register(self, callbacks: CallbackMetaList, resolver):
        executor_list = self[callbacks]
        executor_list.add(callbacks, resolver)
        return executor_list

    def __getitem__(self, callbacks: CallbackMetaList) -> CallbacksExecutor:
        return self._registry[callbacks]

    def build_register_function_for_resolver(self, resolver):
        def register(
            meta_list: CallbackMetaList,
            meta: CallbackMeta,
            prepend: bool = False,
        ):
            return self[meta_list].add_one(meta, resolver, prepend=prepend)

        return register
