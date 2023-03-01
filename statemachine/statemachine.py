from typing import Any, Dict, List, TYPE_CHECKING  # noqa: F401, I001
from collections import deque

from .dispatcher import ObjectConfig
from .dispatcher import resolver_factory
from .event import Event
from .event_data import TriggerData
from .event_data import EventData
from .exceptions import InvalidStateValue
from .exceptions import InvalidDefinition
from .exceptions import TransitionNotAllowed
from .factory import StateMachineMetaclass
from .model import Model
from .transition import Transition
from .utils import ugettext as _


if TYPE_CHECKING:
    from .state import State  # noqa: F401


class StateMachine(metaclass=StateMachineMetaclass):

    TransitionNotAllowed = TransitionNotAllowed  # shortcut for handling exceptions

    _events = {}  # type: Dict[Any, Any]
    states = []  # type: List[State]
    states_map = {}  # type: Dict[Any, State]

    def __init__(self, model=None, state_field="state", start_value=None, queued=False):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value
        self._queued = queued
        self._external_queue = deque()

        if self._abstract:
            raise InvalidDefinition(_("There are no states or transitions."))

        initial_transition = Transition(
            None, self._get_initial_state(), event="__initial__"
        )
        self._setup(initial_transition)
        self._activate_initial_state(initial_transition)

    def __repr__(self):
        current_state_id = self.current_state.id if self.current_state else None
        return (
            f"{type(self).__name__}(model={self.model!r}, state_field={self.state_field!r}, "
            f"current_state={current_state_id!r})"
        )

    def _get_initial_state(self):
        current_state_value = (
            self.start_value if self.start_value else self.initial_state.value
        )
        try:
            return self.states_map[current_state_value]
        except KeyError as err:
            raise InvalidStateValue(current_state_value) from err

    def _activate_initial_state(self, initial_transition):
        if self.current_state_value is None:
            # send an one-time event `__initial__` to enter the current state.
            # current_state = self.current_state
            initial_transition.before.clear()
            initial_transition.on.clear()
            initial_transition.after.clear()

            event_data = EventData(
                trigger_data=TriggerData(
                    machine=self,
                    event=initial_transition.event,
                ),
                transition=initial_transition,
            )
            self._activate(event_data)

    def _get_protected_attrs(self):
        return {
            "_abstract",
            "model",
            "state_field",
            "start_value",
            "initial_state",
            "final_states",
            "states",
            "_events",
            "states_map",
            "send",
        } | {s.id for s in self.states}

    def _visit_states_and_transitions(self, visitor):
        for state in self.states:
            visitor(state)
            for transition in state.transitions:
                visitor(transition)

    def _setup(self, initial_transition):
        machine = ObjectConfig(self, skip_attrs=self._get_protected_attrs())
        model = ObjectConfig(self.model, skip_attrs={self.state_field})
        default_resolver = resolver_factory(machine, model)

        # clone states and transitions to avoid sharing callbacks references between instances
        self.states_map = {
            state.value: state.clone()._setup(self, default_resolver)
            for state in self.states
        }
        self.states = list(self.states_map.values())

        for state in self.states:
            for transition in state.transitions:
                transition._setup(self, default_resolver)

        initial_transition._setup(self, default_resolver)
        self.add_observer(machine, model)

    def add_observer(self, *observers):
        resolvers = [resolver_factory(ObjectConfig.from_obj(o)) for o in observers]
        self._visit_states_and_transitions(lambda x: x._add_observer(*resolvers))
        return self

    def _repr_html_(self):
        return f'<div class="statemachine">{self._repr_svg_()}</div>'

    def _repr_svg_(self):
        return self._graph().create_svg().decode()

    def _graph(self):
        from .contrib.diagram import DotGraphMachine

        return DotGraphMachine(self).get_graph()

    @property
    def current_state_value(self):
        value = getattr(self.model, self.state_field, None)
        return value

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        return self.states_map.get(self.current_state_value, None)

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def events(self):
        return self.__class__.events

    @property
    def allowed_events(self):
        "get the callable proxy of the current allowed events"
        return [
            getattr(self, event)
            for event in self.current_state.transitions.unique_events
        ]

    def _process(self, trigger):  # noqa: C901
        # Check if the machine is running in "queued" mode
        if not self._queued:
            # If the queue is not empty, raise an exception as something is wrong
            if len(self._external_queue) > 0:
                raise TransitionNotAllowed("Queue not empty.")
            # If the queue is empty, execute the trigger immediately
            return trigger()

        # If the machine is in "queued" mode, add the trigger to the queue
        self._external_queue.append(trigger)
        # If there is already a trigger in the queue,
        # only return as the processing loop should already be running
        if len(self._external_queue) > 1:
            return

        # Execute the triggers in the queue in order until the queue is empty
        while self._external_queue:
            # Get the next trigger in the queue
            queued_trigger = self._external_queue[0]
            try:
                # Execute the trigger and remove it from the queue if successful
                queued_trigger()
                self._external_queue.popleft()
            except Exception:
                # If the trigger raises an exception, clear the queue and re-raise the exception
                self._external_queue.clear()
                raise

    def _activate(self, event_data: EventData):
        transition = event_data.transition
        source = event_data.state
        target = transition.target

        result = transition.before.call(*event_data.args, **event_data.extended_kwargs)
        if source is not None and not transition.internal:
            source.exit.call(*event_data.args, **event_data.extended_kwargs)

        result += transition.on.call(*event_data.args, **event_data.extended_kwargs)

        self.current_state = target
        event_data.state = target

        if not transition.internal:
            target.enter.call(*event_data.args, **event_data.extended_kwargs)
        transition.after.call(*event_data.args, **event_data.extended_kwargs)

        if len(result) == 0:
            result = None
        elif len(result) == 1:
            result = result[0]

        return result

    def send(self, event, *args, **kwargs):
        event = Event(event)
        return event.trigger(self, *args, **kwargs)
