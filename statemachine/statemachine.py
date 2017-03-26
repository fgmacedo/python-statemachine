# coding: utf-8

from collections import OrderedDict
from . import registry
try:
    from django.utils.translation import ugettext as _
except Exception:
    def _(text):
        return text


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

    def __init__(self, source, destination, identifier=None, validators=None):
        self.source = source
        self.destination = destination
        self.identifier = identifier
        self.validators = validators or []

    def __repr__(self):
        return "{}({!r}, {!r}, identifier={!r})".format(
            type(self).__name__, self.source, self.destination, self.identifier)

    def __or__(self, other):
        return CombinedTransition(self, other, identifier=self.identifier)

    def __contribute_to_class__(self, managed, identifier):
        self.managed = managed
        self.identifier = identifier

    def __get__(self, instance, owner):
        def callable(*args, **kwargs):
            return self._run(instance, *args, **kwargs)

        return CallableInstance(self, func=callable)

    def __set__(self, instance, value):
        "does nothing (not allow overriding)"

    def _can_run(self, instance):
        return instance.current_state == self.source

    def _run(self, instance, *args, **kwargs):
        if not self._can_run(instance):
            raise LookupError(
                _("Can't {} when in {}.").format(
                    self.identifier,
                    instance.current_state.name
                )
            )

        self._validate(*args, **kwargs)
        return instance._activate(self, *args, **kwargs)

    def _validate(self, *args, **kwargs):
        for validator in self.validators:
            validator(*args, **kwargs)


class CombinedTransition(Transition):

    @property
    def _left(self):
        return self.source

    @property
    def _right(self):
        return self.destination

    def __contribute_to_class__(self, managed, identifier):
        super(CombinedTransition, self).__contribute_to_class__(managed, identifier)
        self._left.__contribute_to_class__(managed, identifier)
        self._right.__contribute_to_class__(managed, identifier)

    def _can_run(self, instance):
        return instance.current_state in [self._left.source, self._right.source]

    def _run(self, instance, *args, **kwargs):
        if not self._can_run(instance):
            raise LookupError(
                _("Can't {} when in {}.").format(
                    self.identifier,
                    instance.current_state.name
                )
            )

        self._validate(*args, **kwargs)
        transition = self._left if instance.current_state == self._left.source else self._right
        return transition._run(instance, *args, **kwargs)


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

    def to(self, state):
        transition = Transition(self, state)
        self.transitions.append(transition)
        return transition

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
        return "{}(model={!r}, state_field={!r})".format(
            type(self).__name__, self.model, self.state_field,
        )

    def check(self):
        if not self.states:
            raise ValueError(_('There are no states.'))

        if not self.transitions:
            raise ValueError(_('There are no transitions.'))

        initials = [s for s in self.states if s.initial]
        if len(initials) != 1:
            raise ValueError(_('There should be one and only one initial state. '
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
            raise ValueError(_("{!r} is not a valid state value.").format(value))
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
        on_event = getattr(self, 'on_{}'.format(transition.identifier), None)
        result = on_event(*args, **kwargs) if callable(on_event) else None
        self.current_state = transition.destination
        return result

    def get_transition(self, transition_identifier):
        transition = getattr(self, transition_identifier, None)
        if not hasattr(transition, 'source') or not callable(transition):
            raise ValueError(
                '{!r} is not a valid transition identifier'.format(transition_identifier))
        return transition

    def run(self, transition_identifier, *args, **kwargs):
        transition = self.get_transition(transition_identifier)
        return transition(*args, **kwargs)


StateMachine = StateMachineMetaclass('StateMachine', (BaseStateMachine, ), {})
