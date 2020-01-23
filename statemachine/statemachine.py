# coding: utf-8

from typing import Any, List, Dict, Optional, TypeVar, Text, Generic

from . import registry
from .exceptions import (
    StateMachineError,
    InvalidDefinition,
    InvalidStateValue,
    InvalidDestinationState,
    InvalidTransitionIdentifier,
    TransitionNotAllowed,
    MultipleStatesFound,
    MultipleTransitionCallbacksFound,
)
from .utils import ugettext as _


V = TypeVar('V')


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
        self.__dict__['target'] = target
        self.__dict__['func'] = func
        self.__dict__['kwargs'] = kwargs
        for k, v in kwargs.items():
            self.__dict__[k] = v

    def __getattr__(self, value):
        return getattr(self.target, value)

    def __setattr__(self, key, value):
        setattr(self.target, key, value)

    def __repr__(self):
        return "{}({}, func={!r}, **{!r})".format(
            type(self).__name__,
            repr(self.target),
            self.func,
            self.kwargs,
        )

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class Transition(object):
    """
    A transition holds reference to the source and destinations states.
    """

    def __init__(self, *states, **options):
        self.source = states[0]
        self.destinations = states[1:]
        self.identifier = options.get('identifier')
        self.validators = options.get('validators', [])
        self.on_execute = options.get('on_execute')

    def __repr__(self):
        return "{}({!r}, {!r}, identifier={!r})".format(
            type(self).__name__, self.source, self.destinations, self.identifier)

    def __or__(self, other):
        return CombinedTransition(self, other, identifier=self.identifier)

    def __get__(self, machine, owner):
        def transition_callback(*args, **kwargs):
            return self._run(machine, *args, **kwargs)

        return CallableInstance(self, func=transition_callback)

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def __call__(self, f):
        if not callable(f):
            raise StateMachineError('Transitions can only be called as method decorators.')
        self.on_execute = f
        return self

    def _set_identifier(self, identifier):
        self.identifier = identifier

    def _can_run(self, machine):
        if machine.current_state == self.source:
            return self

    def _verify_can_run(self, machine):
        transition = self._can_run(machine)
        if not transition:
            raise TransitionNotAllowed(self, machine.current_state)
        return transition

    def _run(self, machine, *args, **kwargs):
        self._verify_can_run(machine)
        self._validate(*args, **kwargs)
        return machine._activate(self, *args, **kwargs)

    def _validate(self, *args, **kwargs):
        for validator in self.validators:
            validator(*args, **kwargs)

    def _get_destination_from_result(self, result):
        """
        Try to extract a destination state from ``result`` if it exists.
        """
        destination = None
        if result is None:
            return result, destination
        elif isinstance(result, State):
            destination = result
            result = None
        else:
            try:
                num = len(result)
            except TypeError:
                return result, destination

            if num < 2:
                return result, destination

            if isinstance(result[-1], State):
                result, destination = result[:-1], result[-1]
                if len(result) == 1:
                    result = result[0]

        return result, destination

    def _get_destination(self, result):
        """
        A transition can point to one or more destination states.
        If there is more than 1 state, the transition **must** specify a `on_execution` callback
        that should return the desired state.
        """
        result, destination = self._get_destination_from_result(result)

        if destination is None:
            if len(self.destinations) == 1:
                destination = self.destinations[0]
            else:
                raise MultipleStatesFound(self)

        if destination not in self.destinations:
            raise InvalidDestinationState(self, destination)

        return result, destination


class CombinedTransition(Transition):

    @property
    def _left(self):
        return self.source

    @property
    def _right(self):
        return self.destinations[0]

    def __call__(self, f):
        result = super(CombinedTransition, self).__call__(f)
        self._left.on_execute = self.on_execute
        self._right.on_execute = self.on_execute
        return result

    def _set_identifier(self, identifier):
        super(CombinedTransition, self)._set_identifier(identifier)
        self._left._set_identifier(identifier)
        self._right._set_identifier(identifier)

    def _can_run(self, machine):
        return self._left._can_run(machine) or self._right._can_run(machine)

    def _run(self, machine, *args, **kwargs):
        transition = self._verify_can_run(machine)
        self._validate(*args, **kwargs)
        return transition._run(machine, *args, **kwargs)


class State(object):

    def __init__(self, name, value=None, initial=False):
        # type: (Text, Optional[V], bool) -> None
        self.name = name
        self.value = value
        self._initial = initial
        self.identifier = None  # type: Optional[Text]
        self.transitions = []  # type: List[Transition]

    def __repr__(self):
        return "{}({!r}, identifier={!r}, value={!r}, initial={!r})".format(
            type(self).__name__, self.name, self.identifier, self.value, self.initial
        )

    def _set_identifier(self, identifier):
        self.identifier = identifier
        if not self.value:
            self.value = identifier

    def _to_(self, *states):
        transition = Transition(self, *states)
        self.transitions.append(transition)
        return transition

    def _from_(self, *states):
        combined = None
        for origin in states:
            transition = Transition(origin, self)
            origin.transitions.append(transition)
            if combined is None:
                combined = transition
            else:
                combined |= transition
        return combined

    def _get_proxy_method_to_itself(self, method):
        def proxy(*states):
            return method(*states)

        def proxy_to_itself():
            return proxy(self)

        proxy.itself = proxy_to_itself
        return proxy

    @property
    def to(self):
        return self._get_proxy_method_to_itself(self._to_)

    @property
    def from_(self):
        return self._get_proxy_method_to_itself(self._from_)

    @property
    def initial(self):
        return self._initial


def check_state_factory(state):
    "Return a property that checks if the current state is the desired state"
    @property
    def is_in_state(self):
        # type: (BaseStateMachine) -> bool
        return bool(self.current_state == state)
    return is_in_state


class StateMachineMetaclass(type):

    def __init__(cls, name, bases, attrs):
        super(StateMachineMetaclass, cls).__init__(name, bases, attrs)
        registry.register(cls)
        cls.states = []
        cls.transitions = []
        cls.states_map = {}
        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)

        for state in cls.states:
            setattr(cls, 'is_{}'.format(state.identifier), check_state_factory(state))

    def add_inherited(cls, bases):
        for base in bases:
            for state in getattr(base, 'states', []):
                cls.add_state(state.identifier, state)
            for transition in getattr(base, 'transitions', []):
                cls.add_transition(transition.identifier, transition)

    def add_from_attributes(cls, attrs):
        for key, value in sorted(attrs.items(), key=lambda pair: pair[0]):
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, Transition):
                cls.add_transition(key, value)

    def add_state(cls, identifier, state):
        state._set_identifier(identifier)
        cls.states.append(state)
        cls.states_map[state.value] = state

    def add_transition(cls, identifier, transition):
        transition._set_identifier(identifier)
        cls.transitions.append(transition)


class Model(Generic[V]):

    def __init__(self):
        self.state = None  # type: Optional[V]

    def __repr__(self):
        return 'Model(state={})'.format(self.state)


class BaseStateMachine(object):

    transitions = []  # type: List[Transition]
    states = []  # type: List[State]
    states_map = {}  # type: Dict[Any, State]

    def __init__(self, model=None, state_field='state', start_value=None):
        # type: (Any, str, Optional[V]) -> None
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value

        self.check()

    def __repr__(self):
        return "{}(model={!r}, state_field={!r}, current_state={!r})".format(
            type(self).__name__, self.model, self.state_field,
            self.current_state.identifier,
        )

    def _visit_neighbour_states(self, transition, visited_states):
        for neighbour_state in transition.destinations:
            if neighbour_state not in visited_states:
                self._visitable_states(neighbour_state, visited_states)

    def _visitable_states(self, start_state, visited_states):
        visited_states.append(start_state)

        for transition in start_state.transitions:
            self._visit_neighbour_states(transition, visited_states)
        return visited_states

    def _disconnected_states(self, starting_state):
        visitable_states = self._visitable_states(starting_state, visited_states=[])

        return set(self.states) - set(visitable_states)

    def check(self):
        if not self.states:
            raise InvalidDefinition(_('There are no states.'))

        if not self.transitions:
            raise InvalidDefinition(_('There are no transitions.'))

        initials = [s for s in self.states if s.initial]
        if len(initials) != 1:
            raise InvalidDefinition(_('There should be one and only one initial state. '
                                      'Your currently have these: {!r}'.format(initials)))
        self.initial_state = initials[0]

        disconnected_states = self._disconnected_states(self.initial_state)
        if (disconnected_states):
            raise InvalidDefinition(_('There are unreachable states. '
                                    'The statemachine graph should have a single component. '
                                      'Disconnected states: [{}]'.format(disconnected_states)))

        if self.current_state_value is None:
            if self.start_value:
                self.current_state_value = self.start_value
            else:
                self.current_state_value = self.initial_state.value

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
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        return [
            getattr(self, t.identifier)
            for t in self.current_state.transitions if t._can_run(self)
        ]

    def _activate(self, transition, *args, **kwargs):
        bounded_on_event = getattr(self, 'on_{}'.format(transition.identifier), None)
        on_event = transition.on_execute

        if bounded_on_event and on_event and bounded_on_event != on_event:
            raise MultipleTransitionCallbacksFound(transition)

        result = None
        if callable(bounded_on_event):
            result = bounded_on_event(*args, **kwargs)
        elif callable(on_event):
            result = on_event(self, *args, **kwargs)

        result, destination = transition._get_destination(result)

        bounded_on_exit_state_event = getattr(self, 'on_exit_state', None)
        if callable(bounded_on_exit_state_event):
            bounded_on_exit_state_event(self.current_state)

        bounded_on_exit_specific_state_event = getattr(
            self, 'on_exit_{}'.format(self.current_state.identifier), None)
        if callable(bounded_on_exit_specific_state_event):
            bounded_on_exit_specific_state_event()

        self.current_state = destination

        bounded_on_enter_state_event = getattr(self, 'on_enter_state', None)
        if callable(bounded_on_enter_state_event):
            bounded_on_enter_state_event(destination)

        bounded_on_enter_specific_state_event = getattr(
            self, 'on_enter_{}'.format(destination.identifier), None)
        if callable(bounded_on_enter_specific_state_event):
            bounded_on_enter_specific_state_event()

        return result

    def get_transition(self, transition_identifier):
        # type: (Text) -> CallableInstance
        transition = getattr(self, transition_identifier, None)  # type: CallableInstance
        if not hasattr(transition, 'source') or not callable(transition):
            raise InvalidTransitionIdentifier(transition_identifier)
        return transition

    def run(self, transition_identifier, *args, **kwargs):
        transition = self.get_transition(transition_identifier)
        return transition(*args, **kwargs)


StateMachine = StateMachineMetaclass('StateMachine', (BaseStateMachine, ), {})
