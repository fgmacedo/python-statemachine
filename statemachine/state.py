from copy import deepcopy
from typing import Any

from .callbacks import Callbacks
from .exceptions import StateMachineError
from .i18n import _
from .transition import Transition
from .transition_list import TransitionList


class State:
    """
    A State in a :ref:`StateMachine` describes a particular behavior of the machine.
    When we say that a machine is “in” a state, it means that the machine behaves
    in the way that state describes.

    Args:
        name: A human-readable representation of the state. Default is derived
            from the name of the variable assigned to the state machine class.
            The name is derived from the id using this logic::

                name = id.replace("_", " ").capitalize()

        value: A specific value to the storage and retrieval of states.
            If specified, you can use It to map a more friendly representation to a low-level
            value.
        initial: Set ``True`` if the ``State`` is the initial one. There must be one and only
            one initial state in a statemachine. Defaults to ``False``.
        final: Set ``True`` if represents a final state. A machine can have
            optionally many final states. Final states have no :ref:`transition` starting from It.
            Defaults to ``False``.
        enter: One or more callbacks assigned to be executed when the state is entered.
            See :ref:`actions`.
        exit: One or more callbacks assigned to be executed when the state is exited.
            See :ref:`actions`.

    State is a core component on how this library implements an expressive API to declare
    StateMachines.

    >>> from statemachine import State

    Given a few states...

    >>> draft = State("Draft", initial=True)

    >>> producing = State("Producing")

    >>> closed = State('Closed', final=True)

    Transitions are declared using the :func:`State.to` or :func:`State.from_` (reversed) methods.

    >>> draft.to(producing)
    TransitionList([Transition(State('Draft', ...

    The result is a `TransitionList`.
    Don't worry about this internal class.
    But the good thing is that it implements the ``OR`` operator to combine transitions,
    so you can use the ``|`` syntax to compound a list of transitions and assign
    to the same event.

    You can declare all transitions for a state in one single line ...

    >>> transitions = draft.to(draft) | producing.to(closed)

    ... and you can append additional transitions for a state to previous definitions.

    >>> transitions |= closed.to(draft)

    >>> [(t.source.name, t.target.name) for t in transitions]
    [('Draft', 'Draft'), ('Producing', 'Closed'), ('Closed', 'Draft')]

    There are handy shortcuts that you can use to express this same set of transitions.

    The first one, ``draft.to(draft)``, is also called a :ref:`self-transition`, and can be
    expressed using an alternative syntax:

    >>> draft.to.itself()
    TransitionList([Transition(State('Draft', ...

    You can even pass a list of target states to declare at once all transitions starting
    from the same state.

    >>> transitions = draft.to(draft, producing, closed)

    >>> [(t.source.name, t.target.name) for t in transitions]
    [('Draft', 'Draft'), ('Draft', 'Producing'), ('Draft', 'Closed')]

    """

    def __init__(
        self,
        name: str = "",
        value: Any = None,
        initial: bool = False,
        final: bool = False,
        enter: Any = None,
        exit: Any = None,
    ):
        self.name = name
        self.value = value
        self._initial = initial
        self._final = final
        self._id: str = ""
        self._storage: str = ""
        self.transitions = TransitionList()
        self.enter = Callbacks().add(enter)
        self.exit = Callbacks().add(exit)

    def __eq__(self, other):
        return (
            isinstance(other, State) and self.name == other.name and self.id == other.id
        )

    def __hash__(self):
        return hash(repr(self))

    def _setup(self, machine, resolver):
        self.machine = machine
        self.enter.setup(resolver)
        self.exit.setup(resolver)
        machine.__dict__[self._storage] = self
        return self

    def _add_observer(self, *resolvers):
        for r in resolvers:
            self.enter.add(
                "on_enter_state", resolver=r, prepend=True, suppress_errors=True
            )
            self.enter.add(f"on_enter_{self.id}", resolver=r, suppress_errors=True)
            self.exit.add(
                "on_exit_state", resolver=r, prepend=True, suppress_errors=True
            )
            self.exit.add(f"on_exit_{self.id}", resolver=r, suppress_errors=True)

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.name!r}, id={self.id!r}, value={self.value!r}, "
            f"initial={self.initial!r}, final={self.final!r})"
        )

    def __get__(self, machine, owner):
        if machine and self._storage in machine.__dict__:
            return machine.__dict__[self._storage]
        return self

    def __set__(self, instance, value):
        raise StateMachineError(
            _("State overriding is not allowed. Trying to add '{}' to {}").format(
                value, self.id
            )
        )

    def clone(self):
        return deepcopy(self)

    @property
    def id(self) -> str:
        return self._id

    def _set_id(self, id: str):
        self._id = id
        self._storage = f"_{id}"
        if self.value is None:
            self.value = id
        if not self.name:
            self.name = self._id.replace("_", " ").capitalize()

    def _to_(self, *states: "State", **kwargs):
        transitions = TransitionList(
            Transition(self, state, **kwargs) for state in states
        )
        self.transitions.add_transitions(transitions)
        return transitions

    def _from_(self, *states: "State", **kwargs):
        transitions = TransitionList()
        for origin in states:
            transition = Transition(origin, self, **kwargs)
            origin.transitions.add_transitions(transition)
            transitions.add_transitions(transition)
        return transitions

    def _get_proxy_method_to_itself(self, method):
        def proxy(*states: "State", **kwargs):
            return method(*states, **kwargs)

        def proxy_to_itself(**kwargs):
            return proxy(self, **kwargs)

        proxy.itself = proxy_to_itself
        return proxy

    @property
    def to(self):
        """Create transitions to the given target states."""
        return self._get_proxy_method_to_itself(self._to_)

    @property
    def from_(self):
        """Create transitions from the given target states (reversed)."""
        return self._get_proxy_method_to_itself(self._from_)

    @property
    def initial(self):
        return self._initial

    @property
    def final(self):
        return self._final

    @property
    def is_active(self):
        return self.machine.current_state == self
