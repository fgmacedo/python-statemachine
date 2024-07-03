import warnings
from collections import deque
from copy import deepcopy
from functools import partial
from inspect import isawaitable
from threading import Lock
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List

from statemachine.graph import iterate_states_and_transitions
from statemachine.utils import run_async_from_sync

from .callbacks import CallbacksExecutor
from .callbacks import CallbacksRegistry
from .dispatcher import Listener
from .dispatcher import Listeners
from .engines.async_ import AsyncEngine
from .engines.sync import SyncEngine
from .event import Event
from .event_data import TriggerData
from .exceptions import InvalidDefinition
from .exceptions import InvalidStateValue
from .exceptions import TransitionNotAllowed
from .factory import StateMachineMetaclass
from .i18n import _
from .model import Model

if TYPE_CHECKING:
    from .state import State


class StateMachine(metaclass=StateMachineMetaclass):
    """

    Args:
        model: An optional external object to store state. See :ref:`domain models`.

        state_field (str): The model's field which stores the current state.
            Default: ``state``.

        start_value: An optional start state value if there's no current state assigned
            on the :ref:`domain models`. Default: ``None``.

        rtc (bool): Controls the :ref:`processing model`. Defaults to ``True``
            that corresponds to a **run-to-completion** (RTC) model.

        allow_event_without_transition: If ``False`` when an event does not result in a transition,
            an exception ``TransitionNotAllowed`` will be raised.
            If ``True`` the state machine allows triggering events that may not lead to a state
            :ref:`transition`, including tolerance to unknown :ref:`event` triggers.
            Default: ``False``.

        listeners: An optional list of objects that provies attributes to be used as callbacks.
            See :ref:`listeners` for more details.

    """

    TransitionNotAllowed = TransitionNotAllowed
    """Shortcut for easy exception handling.

    Example::

        try:
            sm.send("an-inexistent-event")
        except sm.TransitionNotAllowed:
            pass
    """

    def __init__(
        self,
        model: Any = None,
        state_field: str = "state",
        start_value: Any = None,
        rtc: bool = True,
        allow_event_without_transition: bool = False,
        listeners: "List[object] | None" = None,
    ):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value
        self.allow_event_without_transition = allow_event_without_transition
        self._external_queue: deque = deque()
        self._callbacks_registry = CallbacksRegistry()
        self._states_for_instance: Dict[State, State] = {}

        self._listeners: Dict[Any, Any] = {}
        """Listeners that provides attributes to be used as callbacks."""

        if self._abstract:
            raise InvalidDefinition(_("There are no states or transitions."))

        self._register_callbacks(listeners or [])

        # Activate the initial state, this only works if the outer scope is sync code.
        # for async code, the user should manually call `await sm.activate_initial_state()`
        # after state machine creation.
        if self.current_state_value is None:
            trigger_data = TriggerData(
                machine=self,
                event="__initial__",
            )
            self._put_nonblocking(trigger_data)

        self._engine = self._get_engine(rtc)

    def _get_engine(self, rtc: bool):
        if self._callbacks_registry.has_async_callbacks:
            return AsyncEngine(self, rtc=rtc)
        else:
            return SyncEngine(self, rtc=rtc)

    def activate_initial_state(self):
        result = self._engine.activate_initial_state()
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def _processing_loop(self):
        return self._engine.processing_loop()

    def __init_subclass__(cls, strict_states: bool = False):
        cls._strict_states = strict_states
        super().__init_subclass__()

    if TYPE_CHECKING:
        """Makes mypy happy with dynamic created attributes"""

        def __getattr__(self, attribute: str) -> Any: ...

    def __repr__(self):
        current_state_id = self.current_state.id if self.current_state_value else None
        return (
            f"{type(self).__name__}(model={self.model!r}, state_field={self.state_field!r}, "
            f"current_state={current_state_id!r})"
        )

    def __deepcopy__(self, memo):
        deepcopy_method = self.__deepcopy__
        lock = self._engine._processing
        with lock:
            self.__deepcopy__ = None
            self._engine._processing = None
            try:
                cp = deepcopy(self, memo)
                cp._engine._processing = Lock()
            finally:
                self.__deepcopy__ = deepcopy_method
                cp.__deepcopy__ = deepcopy_method
                self._engine._processing = lock
        cp._callbacks_registry.clear()
        cp._register_callbacks([])
        cp.add_listener(*cp._listeners.keys())
        return cp

    def _get_initial_state(self):
        current_state_value = self.start_value if self.start_value else self.initial_state.value
        try:
            return self.states_map[current_state_value]
        except KeyError as err:
            raise InvalidStateValue(current_state_value) from err

    def bind_events_to(self, *targets):
        """Bind the state machine events to the target objects."""

        for event in self.events:
            trigger = getattr(self, event.name)
            for target in targets:
                if hasattr(target, event.name):
                    warnings.warn(
                        f"Attribute {event.name!r} already exists on {target!r}. "
                        f"Skipping binding.",
                        UserWarning,
                        stacklevel=2,
                    )
                    continue
                setattr(target, event.name, trigger)

    def _add_listener(self, listeners: "Listeners"):
        register = partial(listeners.resolve, registry=self._callbacks_registry)
        for visited in iterate_states_and_transitions(self.states):
            register(visited._specs)

        return self

    def _register_callbacks(self, listeners: List[object]):
        self._listeners.update({listener: None for listener in listeners})
        self._add_listener(
            Listeners.from_listeners(
                (
                    Listener.from_obj(self, skip_attrs=self._protected_attrs),
                    Listener.from_obj(self.model, skip_attrs={self.state_field}),
                    *(Listener.from_obj(listener) for listener in listeners),
                )
            )
        )

        check_callbacks = self._callbacks_registry.check
        for visited in iterate_states_and_transitions(self.states):
            try:
                check_callbacks(visited._specs)
            except Exception as err:
                raise InvalidDefinition(
                    f"Error on {visited!s} when resolving callbacks: {err}"
                ) from err

        self._callbacks_registry.async_or_sync()

    def add_observer(self, *observers):
        """Add a listener."""
        warnings.warn(
            """The `add_observer` was rebranded to `add_listener`.""",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.add_listener(*observers)

    def add_listener(self, *listeners):
        """Add a listener.

        Listener are a way to generically add behavior to a :ref:`StateMachine` without changing
        its internal implementation.

        .. seealso::

            :ref:`listeners`.
        """
        self._listeners.update({o: None for o in listeners})
        return self._add_listener(
            Listeners.from_listeners(Listener.from_obj(o) for o in listeners)
        )

    def _repr_html_(self):
        return f'<div class="statemachine">{self._repr_svg_()}</div>'

    def _repr_svg_(self):
        return self._graph().create_svg().decode()

    def _graph(self):
        from .contrib.diagram import DotGraphMachine

        return DotGraphMachine(self).get_graph()

    @property
    def current_state_value(self):
        """Get/Set the current :ref:`state` value.

        This is a low level API, that can be used to assign any valid state value
        completely bypassing all the hooks and validations.
        """
        return getattr(self.model, self.state_field, None)

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self) -> "State":
        """Get/Set the current :ref:`state`.

        This is a low level API, that can be to assign any valid state
        completely bypassing all the hooks and validations.
        """

        try:
            state: State = self.states_map[self.current_state_value].for_instance(
                machine=self,
                cache=self._states_for_instance,
            )
            return state
        except KeyError as err:
            if self.current_state_value is None:
                raise InvalidStateValue(
                    self.current_state_value,
                    _(
                        "There's no current state set. In async code, "
                        "did you activate the initial state? "
                        "(e.g., `await sm.activate_initial_state()`)"
                    ),
                ) from err
            raise InvalidStateValue(self.current_state_value) from err

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def events(self):
        return self.__class__.events

    @property
    def allowed_events(self):
        """List of the current allowed events."""
        return [getattr(self, event) for event in self.current_state.transitions.unique_events]

    def _put_nonblocking(self, trigger_data: TriggerData):
        """Put the trigger on the queue without blocking the caller."""
        self._external_queue.append(trigger_data)

    def send(self, event: str, *args, **kwargs):
        """Send an :ref:`Event` to the state machine.

        .. seealso::

            See: :ref:`triggering events`.

        """
        result = self._async_send(event, *args, **kwargs)
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def _async_send(self, event: str, *args, **kwargs):
        """Send an :ref:`Event` to the state machine.

        .. seealso::

            See: :ref:`triggering events`.

        """
        event_instance: Event = Event(event)
        return event_instance.trigger(self, *args, **kwargs)

    def _get_callbacks(self, key) -> CallbacksExecutor:
        return self._callbacks_registry[key]
