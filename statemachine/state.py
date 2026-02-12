from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from weakref import ref

from .callbacks import CallbackGroup
from .callbacks import CallbackPriority
from .callbacks import CallbackSpecList
from .exceptions import InvalidDefinition
from .exceptions import StateMachineError
from .i18n import _
from .transition import Transition
from .transition_list import TransitionList

if TYPE_CHECKING:
    from .statemachine import StateChart


class _TransitionBuilder:
    def __init__(self, state: "State"):
        self._state = state

    def itself(self, **kwargs):
        return self.__call__(self._state, **kwargs)

    def __call__(self, *states: "State", **kwargs):
        raise NotImplementedError


class _ToState(_TransitionBuilder):
    def __call__(self, *states: "State | None", **kwargs):
        transitions = TransitionList(Transition(self._state, state, **kwargs) for state in states)
        self._state.transitions.add_transitions(transitions)
        return transitions


class _FromState(_TransitionBuilder):
    def any(self, **kwargs):
        """Create transitions from all non-final states (reversed)."""
        return self.__call__(AnyState(), **kwargs)

    def __call__(self, *states: "State", **kwargs):
        transitions = TransitionList()
        for origin in states:
            transition = Transition(origin, self._state, **kwargs)
            origin.transitions.add_transitions(transition)
            transitions.add_transitions(transition)
        return transitions


class NestedStateFactory(type):
    def __new__(  # type: ignore [misc]
        cls, classname, bases, attrs, name="", **kwargs
    ) -> "State":
        if not bases:
            return super().__new__(cls, classname, bases, attrs)  # type: ignore [return-value]

        states = []
        callbacks = {}
        for key, value in attrs.items():
            if isinstance(value, State):
                value._set_id(key)
                states.append(value)
            elif isinstance(value, TransitionList):
                value.add_event(key)
            elif callable(value):
                callbacks[key] = value

        return State(name=name, states=states, _callbacks=callbacks, **kwargs)

    @classmethod
    def to(cls, *args: "State", **kwargs) -> "_ToState":  # pragma: no cover
        """Create transitions to the given target states.
        .. note: This method is only a type hint for mypy.
            The actual implementation belongs to the :ref:`State` class.
        """
        return _ToState(State())

    @classmethod
    def from_(cls, *args: "State", **kwargs) -> "_FromState":  # pragma: no cover
        """Create transitions from the given target states (reversed).
        .. note: This method is only a type hint for mypy.
            The actual implementation belongs to the :ref:`State` class.
        """
        return _FromState(State())


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
            If not specified, the default initial state is the first child state in document order.
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

    >>> draft = State(name="Draft", initial=True)

    >>> producing = State("Producing")

    >>> closed = State('Closed', final=True)

    Transitions are declared using the :func:`State.to` or :func:`State.from_` (reversed) methods.

    >>> draft.to(producing)
    TransitionList([Transition('Draft', 'Producing', event=[], internal=False, initial=False)])

    The result is a :ref:`TransitionList`.
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
    TransitionList([Transition('Draft', 'Draft', event=[], internal=False, initial=False)])

    You can even pass a list of target states to declare at once all transitions starting
    from the same state.

    >>> transitions = draft.to(draft, producing, closed)

    >>> [(t.source.name, t.target.name) for t in transitions]
    [('Draft', 'Draft'), ('Draft', 'Producing'), ('Draft', 'Closed')]

    Sometimes it's easier to use the :func:`State.from_` method:

    >>> transitions = closed.from_(draft, producing, closed)

    >>> [(t.source.name, t.target.name) for t in transitions]
    [('Draft', 'Closed'), ('Producing', 'Closed'), ('Closed', 'Closed')]

    """

    class Compound(metaclass=NestedStateFactory):
        "Uses the class namespace to build a :ref:`State` instance of a compound state"

    class Parallel(metaclass=NestedStateFactory, parallel=True):
        "Uses the class namespace to build a :ref:`State` instance of a parallel state"

    def __init__(
        self,
        name: str = "",
        value: Any = None,
        initial: bool = False,
        final: bool = False,
        parallel: bool = False,
        states: "List[State] | None" = None,
        history: "List[HistoryState] | None" = None,
        enter: Any = None,
        exit: Any = None,
        donedata: Any = None,
        _callbacks: Any = None,
    ):
        self.name = name
        self.value = value
        self._parallel = parallel
        self.states = states or []
        self.history = history or []
        self.is_atomic = bool(not self.states)
        self._initial = initial
        self._final = final
        self.is_active = False
        self._id: str = ""
        self._callbacks = _callbacks
        self.parent: "State | None" = None
        self.transitions = TransitionList()
        self._specs = CallbackSpecList()
        self.enter = self._specs.grouper(CallbackGroup.ENTER).add(
            enter, priority=CallbackPriority.INLINE
        )
        self.exit = self._specs.grouper(CallbackGroup.EXIT).add(
            exit, priority=CallbackPriority.INLINE
        )
        if donedata is not None:
            if not final:
                raise InvalidDefinition(_("'donedata' can only be specified on final states."))
            self.enter.add(donedata, priority=CallbackPriority.INLINE)
        self.document_order = 0
        self._init_states()

    def _init_states(self):
        for state in self.states:
            state.parent = self
            state._initial = state.initial or self.parallel
            setattr(self, state.id, state)

        for history in self.history:
            history.parent = self
            setattr(self, history.id, history)

    def __eq__(self, other):
        return (
            isinstance(other, State)
            and self.name == other.name
            and self.id == other.id
            or (self.value == other)
        )

    def __hash__(self):
        return hash(repr(self))

    def _setup(self):
        self.enter.add("on_enter_state", priority=CallbackPriority.GENERIC, is_convention=True)
        self.enter.add(f"on_enter_{self.id}", priority=CallbackPriority.NAMING, is_convention=True)
        self.exit.add("on_exit_state", priority=CallbackPriority.GENERIC, is_convention=True)
        self.exit.add(f"on_exit_{self.id}", priority=CallbackPriority.NAMING, is_convention=True)

    def _on_event_defined(self, event: str, transition: Transition, states: List["State"]):
        """Called by statemachine factory when an event is defined having a transition
        starting from this state.
        """
        pass

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.name!r}, id={self.id!r}, value={self.value!r}, "
            f"initial={self.initial!r}, final={self.final!r}, parallel={self.parallel!r})"
        )

    def __str__(self):
        return self.name

    def __get__(self, machine, owner):
        if machine is None:
            return self
        return self.for_instance(machine=machine, cache=machine._states_for_instance)

    def __set__(self, instance, value):
        raise StateMachineError(
            _("State overriding is not allowed. Trying to add '{}' to {}").format(value, self.id)
        )

    def for_instance(self, machine: "StateChart", cache: Dict["State", "State"]) -> "State":
        if self not in cache:
            cache[self] = InstanceState(self, machine)

        return cache[self]

    @property
    def id(self) -> str:
        return self._id

    def _set_id(self, id: str) -> "State":
        self._id = id
        if self.value is None:
            self.value = id
        if not self.name:
            self.name = self._id.replace("_", " ").capitalize()

        return self

    @property
    def to(self) -> _ToState:
        """Create transitions to the given target states."""
        return _ToState(self)

    @property
    def from_(self) -> _FromState:
        """Create transitions from the given target states (reversed)."""
        return _FromState(self)

    @property
    def initial(self):
        return self._initial

    @property
    def final(self):
        return self._final

    @property
    def parallel(self):
        return self._parallel

    @property
    def is_compound(self):
        return bool(self.states) and not self.parallel

    @property
    def is_history(self):
        return isinstance(self, HistoryState)

    def ancestors(self, parent: "State | None" = None) -> Generator["State", None, None]:  # noqa: UP043
        selected = self.parent
        while selected:
            if parent and selected == parent:
                break
            yield selected
            selected = selected.parent

    def is_descendant(self, state: "State") -> bool:
        return state in self.ancestors()


class InstanceState(State):
    """ """

    def __init__(
        self,
        state: State,
        machine: "StateChart",
    ):
        self._state = ref(state)
        self._machine = ref(machine)
        self._init_states()

    @property
    def name(self):
        return self._state().name

    @property
    def value(self):
        return self._state().value

    @property
    def transitions(self):
        return self._state().transitions

    @property
    def enter(self):
        return self._state().enter

    @property
    def exit(self):
        return self._state().exit

    def __eq__(self, other):
        return self._state() == other

    def __hash__(self):
        return hash(repr(self._state()))

    def __repr__(self):
        return repr(self._state())

    @property
    def initial(self):
        return self._state()._initial

    @property
    def final(self):
        return self._state()._final

    @property
    def id(self) -> str:
        return (self._state() or self)._id

    @property
    def is_active(self):
        return self.value in self._machine().configuration_values

    @property
    def is_atomic(self):
        return self._state().is_atomic

    @property
    def parent(self):
        return self._state().parent

    @property
    def states(self):
        return self._state().states

    @property
    def history(self):
        return self._state().history

    @property
    def parallel(self):
        return self._state().parallel

    @property
    def is_compound(self):
        return self._state().is_compound

    @property
    def document_order(self):
        return self._state().document_order


class AnyState(State):
    """A special state that works as a "ANY" placeholder.

    It is used as the "From" state of a transtion,
    until the state machine class is evaluated.
    """

    def _on_event_defined(self, event: str, transition: Transition, states: List[State]):
        for state in states:
            if state.final:
                continue
            new_transition = transition._copy_with_args(source=state, event=event)

            state.transitions.add_transitions(new_transition)


class HistoryState(State):
    def __init__(self, name: str = "", value: Any = None, deep: bool = False):
        super().__init__(name=name, value=value)
        self.deep = deep
        self.is_active = False
