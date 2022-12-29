# coding: utf-8
import warnings
from collections import OrderedDict
from typing import Any, List, Dict, Optional, TypeVar, Text, Generic

from . import registry
from .exceptions import (
    InvalidDefinition,
    InvalidStateValue,
    InvalidTransitionIdentifier,
    TransitionNotAllowed,
    MultipleTransitionCallbacksFound,
)
from .utils import ugettext as _, ensure_iterable, call_with_args
from .graph import visit_connected_states


V = TypeVar("V")


class CallableInstance(object):
    """
    Proxy that can override params by passing in kwargs and can run a callable.

    When a user wants to call a transition from the state machine, the instance
    of the state machine is only know at the __get__ method of the transition,
    since it's a property descriptor.

    To allow concurrency, we cannot store the current instance in the
    descriptor, as it permits only one instance to call a transition  at a
    time.

    The CallableInstance is a proxy that acts like the original object, but has
    a __call__ method that can run a lambda function.

    And you can customize/override any attr by defining **kwargs.
    """

    def __init__(self, target, func, **kwargs):
        self.__dict__["target"] = target
        self.__dict__["func"] = func
        self.__dict__["kwargs"] = kwargs
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def __getattr__(self, value):
        return getattr(self.target, value)

    def __setattr__(self, key, value):
        setattr(self.target, key, value)

    def __repr__(self):
        return "{}({}, func={!r}, **{!r})".format(
            type(self).__name__, repr(self.target), self.func, self.kwargs,
        )

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class ConditionWrapper(object):
    def __init__(self, func, expected_value=True):
        self.func = func
        self.expected_value = expected_value
        self._predicate = None

    def check(self, machine):
        self._predicate = machine.ensure_callable(self.func)

    def __call__(self, event_data):
        return self._predicate(event_data) == self.expected_value


class Transition(object):
    """
    A transition holds reference to the source and destination state.
    """

    def __init__(
        self,
        source,
        destination,
        trigger=None,
        validators=None,
        conditions=None,
        unless=None,
        on_execute=None,
    ):
        self.source = source
        self.destination = destination
        self.trigger = trigger
        self.validators = validators if validators is not None else []
        self.on_execute = on_execute
        self.conditions = []
        self._add_conditions(conditions)
        self._add_conditions(unless, expected_value=False)

    def _add_conditions(self, conditions, expected_value=True):
        if conditions is not None:
            conditions = ensure_iterable(conditions)
            for predicate in conditions:
                self.conditions.append(
                    ConditionWrapper(predicate, expected_value=expected_value)
                )

    def __repr__(self):
        return "{}({!r}, {!r}, trigger={!r})".format(
            type(self).__name__, self.source, self.destination, self.trigger
        )

    def __eq__(self, other):
        params = ["source", "destination", "trigger"]
        return all(getattr(self, attr) == getattr(other, attr) for attr in params)

    def _check(self, machine):
        """Validate configuracions"""
        for condition in self.conditions:
            condition.check(machine)

    def _validate(self, *args, **kwargs):
        for validator in self.validators:
            validator(*args, **kwargs)

    def _eval_conditions(self, event_data):
        return all(condition(event_data) for condition in self.conditions)

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `trigger` instead", DeprecationWarning
        )
        return self.trigger

    def execute(self, event_data):
        self._validate(*event_data.args, **event_data.kwargs)
        if not self._eval_conditions(event_data):
            return False

        result = event_data.machine._activate(event_data)
        event_data.result = result
        return True


class TransitionList(object):
    def __init__(self, *transitions):
        self.transitions = list(*transitions)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.transitions)

    def __or__(self, other):
        self.add_transitions(other)
        return self

    def add_transitions(self, transition):
        if isinstance(transition, TransitionList):
            transition = transition.transitions
        transitions = ensure_iterable(transition)

        for transition in transitions:
            if transition not in self.transitions:
                self.transitions.append(transition)

        return self

    def __getitem__(self, index):
        return self.transitions[index]

    def __len__(self):
        return len(self.transitions)

    def __call__(self, f):
        for transition in self.transitions:
            transition.on_execute = f
        return self


class State(object):
    """
    A state in a state machine describes a particular behaviour of the machine.
    When we say that a machine is “in” a state, it means that the machine behaves
    in the way that state describes.
    """
    def __init__(self, name, value=None, initial=False, final=False):
        # type: (Text, Optional[V], bool, bool) -> None
        self.name = name
        self.value = value
        self._initial = initial
        self.identifier = None  # type: Optional[Text]
        self.transitions = TransitionList()
        self._final = final

    def __repr__(self):
        return "{}({!r}, identifier={!r}, value={!r}, initial={!r}, final={!r})".format(
            type(self).__name__,
            self.name,
            self.identifier,
            self.value,
            self.initial,
            self.final,
        )

    def __get__(self, machine, owner):
        return self

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def _set_identifier(self, identifier):
        self.identifier = identifier
        if self.value is None:
            self.value = identifier

    def _to_(self, *states, **kwargs):
        conditions = kwargs.get("conditions", None)
        unless = kwargs.get("unless", None)
        transitions = TransitionList(
            Transition(self, state, conditions=conditions, unless=unless)
            for state in states
        )
        self.transitions.add_transitions(transitions)
        return transitions

    def _from_(self, *states, **kwargs):
        conditions = kwargs.get("conditions", None)
        unless = kwargs.get("unless", None)
        transitions = TransitionList()
        for origin in states:
            transition = Transition(origin, self, conditions=conditions, unless=unless)
            origin.transitions.add_transitions(transition)
            transitions.add_transitions(transition)
        return transitions

    def _get_proxy_method_to_itself(self, method):
        def proxy(*states, **kwargs):
            return method(*states, **kwargs)

        def proxy_to_itself(**kwargs):
            return proxy(self, **kwargs)

        proxy.itself = proxy_to_itself
        return proxy

    @property
    def to(self):
        """Create transitions to the given destination states.

        .. code::

            <origin_state>.to(*<destination_state>)

        """
        return self._get_proxy_method_to_itself(self._to_)

    @property
    def from_(self):
        return self._get_proxy_method_to_itself(self._from_)

    @property
    def initial(self):
        return self._initial

    @property
    def final(self):
        return self._final


def check_state_factory(state):
    "Return a property that checks if the current state is the desired state"

    @property
    def is_in_state(self):
        # type: (BaseStateMachine) -> bool
        return bool(self.current_state == state)

    return is_in_state


class EventData(object):
    def __init__(self, machine, event, *args, **kwargs):
        self.machine = machine
        self.event = event
        self.state = None
        self.model = None
        self.transition = None
        self.executed = False

        # runtime and error
        self.args = args
        self.kwargs = kwargs
        self.error = None
        self.result = None

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.__dict__)


class OrderedDefaultDict(OrderedDict):  # python <= 3.5 compat layer
    factory = TransitionList

    def __missing__(self, key):
        self[key] = value = self.factory()
        return value


class Event(object):
    def __init__(self, name):
        self.name = name
        self._transitions = OrderedDefaultDict()

    def __repr__(self):
        return "{}({!r}, {!r})".format(
            type(self).__name__, self.name, self._transitions
        )

    def __get__(self, machine, owner):
        def trigger_callback(*args, **kwargs):
            return self.trigger(machine, *args, **kwargs)

        return CallableInstance(self, func=trigger_callback)

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def add_transition(self, transition):
        transition.trigger = self.name
        self._transitions[transition.source].add_transitions(transition)

    def add_transitions(self, transitions):
        transitions = ensure_iterable(transitions)
        for transition in transitions:
            self.add_transition(transition)

    @property
    def identifier(self):
        warnings.warn(
            "identifier is deprecated. Use `name` instead", DeprecationWarning
        )
        return self.name

    @property
    def validators(self):
        warnings.warn(
            "`validators` is deprecated. Use `conditions` instead", DeprecationWarning
        )
        return list(
            {
                validator
                for transition in self.transitions
                for validator in transition.validators
            }
        )

    @validators.setter
    def validators(self, value):
        warnings.warn(
            "`validators` is deprecated. Use `conditions` instead", DeprecationWarning
        )
        for transition in self.transitions:
            transition.validators = value

    @property
    def transitions(self):
        return [
            transition
            for transition_list in self._transitions.values()
            for transition in transition_list
        ]

    def _check_is_valid_source(self, state):
        if state not in self._transitions:
            raise TransitionNotAllowed(self, state)

    def trigger(self, machine, *args, **kwargs):
        event_data = EventData(machine, self, *args, **kwargs)

        def trigger_wrapper():
            """Wrapper that captures event_data as closure."""
            return self._trigger(event_data)

        return machine._process(trigger_wrapper)

    def _trigger(self, event_data):
        event_data.state = event_data.machine.current_state
        event_data.model = event_data.machine.model

        try:
            self._check_is_valid_source(event_data.state)
            self._process(event_data)
        except Exception as error:
            event_data.error = error
            # TODO: Log errors
            # TODO: Allow exception handlers
            raise
        return event_data.result

    def _process(self, event_data):
        for transition in self._transitions[event_data.state]:
            event_data.transition = transition
            if transition.execute(event_data):
                event_data.executed = True
                break


class StateMachineMetaclass(type):
    def __init__(cls, name, bases, attrs):
        super(StateMachineMetaclass, cls).__init__(name, bases, attrs)
        registry.register(cls)
        cls.states = []
        cls._events = OrderedDict()
        cls.states_map = {}
        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)

        for state in cls.states:
            setattr(cls, "is_{}".format(state.identifier), check_state_factory(state))

    def add_inherited(cls, bases):
        for base in bases:
            for state in getattr(base, "states", []):
                cls.add_state(state.identifier, state)

            events = getattr(base, "_events", {})
            for event in events.values():
                cls.add_event(event.name, event.transitions)

    def add_from_attributes(cls, attrs):
        for key, value in sorted(attrs.items(), key=lambda pair: pair[0]):
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, (Transition, TransitionList)):
                cls.add_event(key, value)

    def add_state(cls, identifier, state):
        state._set_identifier(identifier)
        cls.states.append(state)
        cls.states_map[state.value] = state

    def add_event(cls, trigger, transitions):
        if trigger not in cls._events:
            event = Event(trigger)
            cls._events[trigger] = event
            setattr(cls, trigger, event)  # bind event to the class
        else:
            event = cls._events[trigger]

        event.add_transitions(transitions)
        return event

    @property
    def transitions(self):
        warnings.warn(
            "Class level property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return list(self._events.values())


class Model(Generic[V]):
    def __init__(self):
        self.state = None  # type: Optional[V]

    def __repr__(self):
        return "Model(state={})".format(self.state)


class BaseStateMachine(object):

    _events = {}  # type: Dict[Any, Any]
    states = []  # type: List[State]
    states_map = {}  # type: Dict[Any, State]

    def __init__(self, model=None, state_field="state", start_value=None):
        # type: (Any, str, Optional[V]) -> None
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value

        self.check()

    def __repr__(self):
        return "{}(model={!r}, state_field={!r}, current_state={!r})".format(
            type(self).__name__,
            self.model,
            self.state_field,
            self.current_state.identifier,
        )

    def _disconnected_states(self, starting_state):
        visitable_states = set(visit_connected_states(starting_state))
        return set(self.states) - visitable_states

    def _check_transitions(self):
        for state in self.states:
            for transition in state.transitions:
                transition._check(self)

    def check(self):
        if not self.states:
            raise InvalidDefinition(_("There are no states."))

        if not self._events:
            raise InvalidDefinition(_("There are no events."))

        initials = [s for s in self.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {!r}".format(initials)
                )
            )
        self.initial_state = initials[0]

        if self.current_state_value is None:
            if self.start_value:
                self.current_state_value = self.start_value
            else:
                self.current_state_value = self.initial_state.value

        disconnected_states = self._disconnected_states(self.initial_state)
        if disconnected_states:
            raise InvalidDefinition(
                _(
                    "There are unreachable states. "
                    "The statemachine graph should have a single component. "
                    "Disconnected states: [{}]".format(disconnected_states)
                )
            )

        self._check_transitions()

        final_state_with_invalid_transitions = [
            state for state in self.final_states if state.transitions
        ]

        if final_state_with_invalid_transitions:
            raise InvalidDefinition(
                _(
                    "Final state does not should have defined "
                    "transitions starting from that state"
                )
            )

    def ensure_callable(self, attr):
        """ Ensure that `attr` is a callable, if not, tries to retrieve one from model or machine.
        Args:
            attr (str or callable): A property/method name or a callable.
        """
        if callable(attr) or isinstance(attr, property):
            return attr

        func = getattr(self, attr, None)
        if func is None:
            func = getattr(self.model, attr, None)

        if func is None:
            raise InvalidDefinition(
                _("Did not found name '{}' from model or statemachine".format(attr))
            )
        if not callable(func):

            def wrapper(*args, **kwargs):
                return func

            return wrapper

        return func

    @property
    def final_states(self):
        return [state for state in self.states if state.final]

    @property
    def current_state_value(self):
        # type: () -> V
        value = getattr(self.model, self.state_field, None)  # type: V
        return value

    @current_state_value.setter
    def current_state_value(self, value):
        # type: (V) -> None
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        # type: () -> State
        return self.states_map[self.current_state_value]

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

    @property
    def transitions(self):
        warnings.warn(
            "Property `transitions` is deprecated. Use `events` instead.",
            DeprecationWarning,
        )
        return self.__class__.transitions

    @property
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        return [getattr(self, t.trigger) for t in self.current_state.transitions]

    def _process(self, trigger):
        """This method will also handle execution queue"""
        return trigger()

    def _activate(self, event_data):
        transition = event_data.transition
        args = event_data.args
        kwargs = event_data.kwargs
        bounded_on_event = getattr(self, "on_{}".format(transition.trigger), None)
        on_event = transition.on_execute

        if bounded_on_event and on_event and bounded_on_event != on_event:
            raise MultipleTransitionCallbacksFound(transition)

        result = None
        if callable(bounded_on_event):
            result = bounded_on_event(*args, **kwargs)
        elif callable(on_event):
            result = on_event(self, *args, **kwargs)

        destination = transition.destination

        bounded_on_exit_state_event = getattr(self, "on_exit_state", None)
        if callable(bounded_on_exit_state_event):
            bounded_on_exit_state_event(self.current_state)

        bounded_on_exit_specific_state_event = getattr(
            self, "on_exit_{}".format(self.current_state.identifier), None
        )

        if callable(bounded_on_exit_specific_state_event):
            call_with_args(bounded_on_exit_specific_state_event, *args, **kwargs)

        self.current_state = destination

        bounded_on_enter_state_event = getattr(self, "on_enter_state", None)
        if callable(bounded_on_enter_state_event):
            bounded_on_enter_state_event(destination)

        bounded_on_enter_specific_state_event = getattr(
            self, "on_enter_{}".format(destination.identifier), None
        )
        if callable(bounded_on_enter_specific_state_event):
            call_with_args(bounded_on_enter_specific_state_event, *args, **kwargs)

        return result

    def get_event(self, trigger):
        # type: (Text) -> CallableInstance
        event = getattr(self, trigger, None)  # type: CallableInstance
        if trigger not in self._events or event is None:
            raise InvalidTransitionIdentifier(trigger)
        return event

    def run(self, trigger, *args, **kwargs):
        event = self.get_event(trigger)
        return event(*args, **kwargs)


StateMachine = StateMachineMetaclass("StateMachine", (BaseStateMachine,), {})
