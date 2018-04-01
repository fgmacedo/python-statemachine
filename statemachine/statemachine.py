# coding: utf-8

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

    def __contribute_to_class__(self, managed, identifier):
        self.managed = managed
        self.identifier = identifier

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

    def __contribute_to_class__(self, managed, identifier):
        super(CombinedTransition, self).__contribute_to_class__(managed, identifier)
        self._left.__contribute_to_class__(managed, identifier)
        self._right.__contribute_to_class__(managed, identifier)

    def _can_run(self, machine):
        return self._left._can_run(machine) or self._right._can_run(machine)

    def _run(self, machine, *args, **kwargs):
        transition = self._verify_can_run(machine)
        self._validate(*args, **kwargs)
        return transition._run(machine, *args, **kwargs)


class State(object):

    def __init__(self, name, value=None, initial=False):
        self.name = name
        self.identifier = None
        self.value = value
        self._initial = initial
        self.transitions = []

    def __repr__(self):
        return "{}({!r}, identifier={!r}, value={!r}, initial={!r})".format(
            type(self).__name__, self.name, self.identifier, self.value, self.initial)

    @property
    def to(self):
        def to_method(*states):
            transition = Transition(self, *states)
            self.transitions.append(transition)
            return transition

        def to_itself():
            return to_method(self)

        to_method.itself = to_itself
        return to_method

    def __contribute_to_class__(self, managed, identifier):
        self.managed = managed
        self.identifier = identifier
        if not self.value:
            self.value = identifier

    @property
    def initial(self):
        return self._initial


def check_state_factory(state):
    "Return a property that checks if the current state is the desired state"
    @property
    def is_in_state(self):
        return self.current_state == state
    return is_in_state


class StateMachineMetaclass(type):

    def __init__(cls, name, bases, attrs):
        super(StateMachineMetaclass, cls).__init__(name, bases, attrs)
        registry.register(cls)
        cls.states = []
        cls.transitions = []
        for key, value in sorted(attrs.items(), key=lambda v: v[0]):
            if isinstance(value, State):
                value.__contribute_to_class__(cls, key)
                cls.states.append(value)
            elif isinstance(value, Transition):
                value.__contribute_to_class__(cls, key)
                cls.transitions.append(value)

        for state in cls.states:
            setattr(cls, 'is_{}'.format(state.identifier), check_state_factory(state))

        cls.states_map = {s.value: s for s in cls.states}


class Model(object):
    state = None

    def __repr__(self):
        return 'Model(state={})'.format(self.state)


class BaseStateMachine(object):

    def __init__(self, model=None, state_field='state', start_value=None):
        self.model = model if model else Model()
        self.state_field = state_field
        self.start_value = start_value

        self.check()

    def __repr__(self):
        return "{}(model={!r}, state_field={!r}, current_state={!r})".format(
            type(self).__name__, self.model, self.state_field,
            self.current_state.identifier,
        )

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

        if self.current_state_value is None:
            if self.start_value:
                self.current_state_value = self.start_value
            else:
                self.current_state_value = self.initial_state.value

    @property
    def current_state_value(self):
        return getattr(self.model, self.state_field, None)

    @current_state_value.setter
    def current_state_value(self, value):
        if value not in self.states_map:
            raise InvalidStateValue(value)
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        return self.states_map[self.current_state_value]

    @property
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        return [
            getattr(self, t.identifier)
            for t in self.current_state.transitions if t._can_run(self)
        ]

    @current_state.setter
    def current_state(self, value):
        self.current_state_value = value.value

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

        bounded_on_enter_state_event = getattr(self, 'on_enter_state', None)
        if callable(bounded_on_enter_state_event):
            bounded_on_enter_state_event(destination)

        bounded_on_exit_specific_state_event = getattr(
            self, 'on_exit_{}'.format(self.current_state.identifier), None)
        if callable(bounded_on_exit_specific_state_event):
            bounded_on_exit_specific_state_event()

        bounded_on_enter_specific_state_event = getattr(
            self, 'on_enter_{}'.format(destination.identifier), None)
        if callable(bounded_on_enter_specific_state_event):
            bounded_on_enter_specific_state_event()

        self.current_state = destination
        return result

    def get_transition(self, transition_identifier):
        transition = getattr(self, transition_identifier, None)
        if not hasattr(transition, 'source') or not callable(transition):
            raise InvalidTransitionIdentifier(transition_identifier)
        return transition

    def run(self, transition_identifier, *args, **kwargs):
        transition = self.get_transition(transition_identifier)
        return transition(*args, **kwargs)


StateMachine = StateMachineMetaclass('StateMachine', (BaseStateMachine, ), {})
