import warnings
from inspect import isawaitable
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import MutableSet

from statemachine.orderedset import OrderedSet

from .callbacks import SPECS_ALL
from .callbacks import SPECS_SAFE
from .callbacks import CallbacksRegistry
from .callbacks import SpecReference
from .dispatcher import Listener
from .dispatcher import Listeners
from .engines.async_ import AsyncEngine
from .engines.sync import SyncEngine
from .event import BoundEvent
from .event_data import TriggerData
from .exceptions import InvalidDefinition
from .exceptions import InvalidStateValue
from .exceptions import TransitionNotAllowed
from .factory import StateMachineMetaclass
from .graph import iterate_states_and_transitions
from .i18n import _
from .model import Model
from .utils import run_async_from_sync

if TYPE_CHECKING:
    from .event import Event
    from .state import State


class StateMachine(metaclass=StateMachineMetaclass):
    """

    Args:
        model: An optional external object to store state. See :ref:`domain models`.

        state_field (str): The model's field which stores the current state.
            Default: ``state``.

        start_value: An optional start state value if there's no current state assigned
            on the :ref:`domain models`. Default: ``None``.

        allow_event_without_transition: If ``False`` when an event does not result in a transition,
            an exception ``TransitionNotAllowed`` will be raised.
            If ``True`` the state machine allows triggering events that may not lead to a state
            :ref:`transition`, including tolerance to unknown :ref:`event` triggers.
            Default: ``False``.

        enable_self_transition_entries: If `False` (default), when a self-transition is selected,
            the state entry/exit actions will not be executed. If `True`, the state entry actions
            will be executed, which is conformant with the SCXML spec.

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
        allow_event_without_transition: bool = False,
        enable_self_transition_entries: bool = False,
        listeners: "List[object] | None" = None,
    ):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value
        self.allow_event_without_transition = allow_event_without_transition
        self.enable_self_transition_entries = enable_self_transition_entries
        self._callbacks = CallbacksRegistry()
        self._states_for_instance: Dict[State, State] = {}
        self._listeners: Dict[int, Any] = {}
        """Listeners that provides attributes to be used as callbacks."""

        if self._abstract:
            raise InvalidDefinition(_("There are no states or transitions."))

        self._register_callbacks(listeners or [])

        # Activate the initial state, this only works if the outer scope is sync code.
        # for async code, the user should manually call `await sm.activate_initial_state()`
        # after state machine creation.
        self._engine = self._get_engine()
        self._engine.start()

    def _get_engine(self):
        if self._callbacks.has_async_callbacks:
            return AsyncEngine(self)

        return SyncEngine(self)

    def activate_initial_state(self):
        result = self._engine.activate_initial_state()
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def _processing_loop(self):
        result = self._engine.processing_loop()
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def __init_subclass__(cls, strict_states: bool = False):
        cls._strict_states = strict_states
        super().__init_subclass__()

    if TYPE_CHECKING:
        """Makes mypy happy with dynamic created attributes"""

        def __getattr__(self, attribute: str) -> Any: ...

    def __repr__(self):
        configuration_ids = [s.id for s in self.configuration]
        return (
            f"{type(self).__name__}(model={self.model!r}, state_field={self.state_field!r}, "
            f"configuration={configuration_ids!r})"
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_callbacks"]
        del state["_states_for_instance"]
        del state["_engine"]
        return state

    def __setstate__(self, state):
        listeners = state.pop("_listeners")
        self.__dict__.update(state)
        self._callbacks = CallbacksRegistry()
        self._states_for_instance: Dict[State, State] = {}

        self._listeners: Dict[Any, Any] = {}

        self._register_callbacks([])
        self.add_listener(*listeners.values())
        self._engine = self._get_engine()

    def _get_initial_state(self):
        initial_state_value = self.start_value if self.start_value else self.initial_state.value
        try:
            return self.states_map[initial_state_value]
        except KeyError as err:
            raise InvalidStateValue(initial_state_value) from err

    def bind_events_to(self, *targets):
        """Bind the state machine events to the target objects."""

        for event in self.events:
            trigger = getattr(self, event)
            for target in targets:
                if hasattr(target, event):
                    warnings.warn(
                        f"Attribute '{event}' already exists on {target!r}. Skipping binding.",
                        UserWarning,
                        stacklevel=2,
                    )
                    continue
                setattr(target, event, trigger)

    def _add_listener(self, listeners: "Listeners", allowed_references: SpecReference = SPECS_ALL):
        registry = self._callbacks
        for visited in iterate_states_and_transitions(self.states):
            listeners.resolve(
                visited._specs,
                registry=registry,
                allowed_references=allowed_references,
            )

        return self

    def _register_callbacks(self, listeners: List[object]):
        self._listeners.update({id(listener): listener for listener in listeners})
        self._add_listener(
            Listeners.from_listeners(
                (
                    Listener.from_obj(self, skip_attrs=self._protected_attrs),
                    Listener.from_obj(self.model, skip_attrs={self.state_field}),
                    *(Listener.from_obj(listener) for listener in listeners),
                )
            )
        )

        check_callbacks = self._callbacks.check
        for visited in iterate_states_and_transitions(self.states):
            try:
                check_callbacks(visited._specs)
            except Exception as err:
                raise InvalidDefinition(
                    f"Error on {visited!s} when resolving callbacks: {err}"
                ) from err

        self._callbacks.async_or_sync()

    def add_observer(self, *observers):
        """Add a listener."""
        warnings.warn(
            """Method `add_observer` has been renamed to `add_listener`.""",
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
        self._listeners.update({id(listener): listener for listener in listeners})
        return self._add_listener(
            Listeners.from_listeners(Listener.from_obj(listener) for listener in listeners),
            allowed_references=SPECS_SAFE,
        )

    def _repr_html_(self):
        return f'<div class="statemachine">{self._repr_svg_()}</div>'

    def _repr_svg_(self):
        return self._graph().create_svg().decode()

    def _graph(self):
        from .contrib.diagram import DotGraphMachine

        return DotGraphMachine(self).get_graph()

    @property
    def configuration(self) -> OrderedSet["State"]:
        if self.current_state_value is None:
            return OrderedSet()

        if not isinstance(self.current_state_value, list):
            return OrderedSet(
                [
                    self.states_map[self.current_state_value].for_instance(
                        machine=self,
                        cache=self._states_for_instance,
                    )
                ]
            )

        return OrderedSet(
            [
                self.states_map[value].for_instance(
                    machine=self,
                    cache=self._states_for_instance,
                )
                for value in self.current_state_value
            ]
        )

    @configuration.setter
    def configuration(self, value: OrderedSet["State"]):
        if len(value) == 0:
            self.current_state_value = None
        elif len(value) == 1:
            self.current_state_value = value.pop().value
        else:
            self.current_state_value = [s.value for s in value]

    @property
    def current_state_value(self):
        """Get/Set the current :ref:`state` value.

        This is a low level API, that can be used to assign any valid state value
        completely bypassing all the hooks and validations.
        """
        return getattr(self.model, self.state_field, None)

    @current_state_value.setter
    def current_state_value(self, value):
        if value is not None and not isinstance(value, list) and value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self) -> "State | MutableSet[State]":
        """Get/Set the current :ref:`state`.

        This is a low level API, that can be to assign any valid state
        completely bypassing all the hooks and validations.
        """
        current_value = self.current_state_value

        try:
            if isinstance(current_value, list):
                return OrderedSet(
                    [
                        self.states_map[value].for_instance(
                            machine=self,
                            cache=self._states_for_instance,
                        )
                        for value in current_value
                    ]
                )

            state: State = self.states_map[current_value].for_instance(
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
    def events(self) -> "List[Event]":
        return [getattr(self, event) for event in self.__class__._events]

    @property
    def allowed_events(self) -> "List[Event]":
        """List of the current allowed events."""
        return [
            getattr(self, event)
            for state in self.configuration
            for event in state.transitions.unique_events
        ]

    def _put_nonblocking(self, trigger_data: TriggerData, internal: bool = False):
        """Put the trigger on the queue without blocking the caller."""
        self._engine.put(trigger_data, internal=internal)

    def send(
        self,
        event: str,
        *args,
        delay: float = 0,
        event_id: "str | None" = None,
        internal: bool = False,
        **kwargs,
    ):
        """Send an :ref:`Event` to the state machine.

        :param event: The trigger for the state machine, specified as an event id string.
        :param args: Additional positional arguments to pass to the event.
        :param delay: A time delay in milliseconds to process the event. Default is 0.
        :param kwargs: Additional keyword arguments to pass to the event.

        .. seealso::

            See: :ref:`triggering events`.
        """
        know_event = getattr(self, event, None)
        event_name = know_event.name if know_event else event
        delay = (
            delay if delay else know_event and know_event.delay or 0
        )  # first the param, then the event, or 0
        event_instance = BoundEvent(
            id=event, name=event_name, delay=delay, internal=internal, _sm=self
        )
        result = event_instance(*args, event_id=event_id, **kwargs)
        if not isawaitable(result):
            return result
        return run_async_from_sync(result)

    def raise_(self, event: str, *args, delay: float = 0, event_id: "str | None" = None, **kwargs):
        """Send an :ref:`Event` to the state machine in the internal event queue.

        Events on the internal queue are processed immediately on the current step of the
        interpreter.

        .. seealso::

            See: :ref:`triggering events`.
        """
        return self.send(event, *args, delay=delay, event_id=event_id, internal=True, **kwargs)

    def cancel_event(self, send_id: str):
        """Cancel all the delayed events with the given ``send_id``."""
        self._engine.cancel_event(send_id)

    @property
    def is_terminated(self):
        return not self._engine.running
