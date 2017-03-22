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

    To allow concurrency, we cannot store the the current instance in the
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

    def __init__(self, source, destination, key=None, validators=None):
        self.source = source
        self.destination = destination
        self.key = key
        self.validators = validators or []

    def __repr__(self):
        return "{}({!r}, {!r}, key={!r})".format(
            type(self).__name__, self.source, self.destination, self.key)

    def __or__(self, other):
        return CombinedTransition(self, other, key=self.key)

    def __contribute_to_class__(self, managed, key):
        self.managed = managed
        self.key = key

    def __get__(self, instance, owner):
        def callable(*args, **kwargs):
            return self._run(instance, *args, **kwargs)

        return CallableInstance(self, func=callable)

    def __set__(self, instance, value):
        # does nothing (not allow overriding)
        pass

    def _can_run(self, instance):
        return instance.current_state == self.source

    def _run(self, instance, *args, **kwargs):
        if not self._can_run(instance):
            raise LookupError(_("Transition is not supported."))

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

    def __contribute_to_class__(self, managed, key):
        super(CombinedTransition, self).__contribute_to_class__(managed, key)
        self._left.__contribute_to_class__(managed, key)
        self._right.__contribute_to_class__(managed, key)

    def _can_run(self, instance):
        return instance.current_state in [self._left.source, self._right.source]

    def _run(self, instance, *args, **kwargs):
        if not self._can_run(instance):
            raise LookupError(_("Transition is not supported."))

        self._validate(*args, **kwargs)
        transition = self._left if instance.current_state == self._left.source else self._right
        return transition._run(instance, *args, **kwargs)


class State(object):

    def __init__(self, name, key=None, initial=False):
        self.name = name
        self.key = key
        self._initial = initial
        self.transitions = []

    def __repr__(self):
        return "{}({!r}, key={!r}, initial={!r})".format(
            type(self).__name__, self.name, self.key, self.initial)

    def to(self, state):
        transition = Transition(self, state)
        self.transitions.append(transition)
        return transition

    def __contribute_to_class__(self, managed, key):
        self.managed = managed
        self.key = key

    @property
    def initial(self):
        return self._initial


class StateMachineMetaclass(type):

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        return OrderedDict()

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

        cls.states_map = {s.key: s for s in cls.states}


class BaseStateMachine(object):

    def __init__(self, model, state_field='state'):
        self.model = model
        self.state_field = state_field

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

        if not self.model:
            raise ValueError(_('There is no model.'))

        initials = [s for s in self.states if s.initial]
        if len(initials) != 1:
            raise ValueError(_('There should be one and only one initial state. '
                               'Your currently have these: {!r}'.format(initials)))
        self.initial_state = initials[0]

        if self.current_state_key is None:
            self.current_state_key = self.initial_state.key

    @property
    def current_state_key(self):
        return getattr(self.model, self.state_field, None)

    @current_state_key.setter
    def current_state_key(self, value):
        if value not in self.states_map:
            raise Exception(_("{!r} is not a valid state value.").format(value))
        setattr(self.model, self.state_field, value)

    @property
    def current_state(self):
        return self.states_map[self.current_state_key]

    @property
    def allowed_transitions(self):
        "get the callable proxy of the current allowed transitions"
        return [
            getattr(self, t.key)
            for t in self.current_state.transitions if t._can_run(self)
        ]

    @current_state.setter
    def current_state(self, value):
        self.current_state_key = value.key

    def _activate(self, transition, *args, **kwargs):
        on_event = getattr(self, 'on_{}'.format(transition.key), None)
        result = on_event(*args, **kwargs) if callable(on_event) else None
        self.current_state = transition.destination
        return result

    def get_transition(self, transition_key):
        transition = getattr(self, transition_key, None)
        if not hasattr(transition, 'source') or not callable(transition):
            raise ValueError('{!r} is not a valid transition key'.format(transition_key))
        return transition

    def run(self, transition_key, *args, **kwargs):
        transition = self.get_transition(transition_key)
        return transition(*args, **kwargs)


StateMachine = StateMachineMetaclass('StateMachine', (BaseStateMachine, ), {})
