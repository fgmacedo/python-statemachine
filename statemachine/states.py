from enum import Enum
from typing import Dict  # deprecated since 3.9: https://peps.python.org/pep-0585/
from typing import Type

from .state import State
from .utils import ensure_iterable

EnumType = Type[Enum]


class States:
    """
    A class representing a collection of :ref:`State` objects.

    Helps creating :ref:`StateMachine`'s :ref:`state` definitions from other
    sources, like an ``Enum`` class, using :meth:`States.from_enum`.

    >>> from statemachine import StateMachine
    >>> class SM(StateMachine):
    ...
    ...     states = States({
    ...         name: State(initial=idx == 0) for idx, name in enumerate(["initial", "final"])
    ...     })
    ...
    ...     finish = states.initial.to(states.final)

    And states can be used as usual.

    >>> sm = SM()
    >>> sm.send("finish")
    >>> sm.current_state.id
    'final'

    """

    def __init__(self, states: "Dict[str, State] | None" = None) -> None:
        """
        Initializes a new instance of the States class.

        Args:
            states: A dictionary mapping keys as ``State.id`` and values :ref:`state` instances.

        Returns:
            None.
        """
        self._states: Dict[str, State] = states if states is not None else {}

    def __repr__(self):
        return f"{list(self)}"

    def __eq__(self, other):
        return list(self) == list(other)

    def __getattr__(self, name: str):
        if name in self._states:
            return self._states[name]
        raise AttributeError(f"{name} not found in {self.__class__.__name__}")

    def __len__(self):
        return len(self._states)

    def __iter__(self):
        return iter(self._states.values())

    def append(self, state):
        self._states[state.id] = state

    def items(self):
        """
        Returns a view object of the states, with pairs of ``(State.id, State)``.

        Args:
            None.

        Returns:
            A view object of the items in the the instance.
        """
        return self._states.items()

    @classmethod
    def from_enum(cls, enum_type: EnumType, initial: Enum, final=None):
        """
        Creates a new instance of the ``States`` class from an enumeration.

        Consider an ``Enum`` type that declares our expected states:

        >>> class Status(Enum):
        ...     pending = 1
        ...     completed = 2

        A :ref:`StateMachine` that uses this enum can be declared as follows:

        >>> from statemachine import StateMachine
        >>> class ApprovalMachine(StateMachine):
        ...
        ...     _ = States.from_enum(Status, initial=Status.pending, final=Status.completed)
        ...
        ...     finish = _.pending.to(_.completed)
        ...
        ...     def on_enter_completed(self):
        ...         print("Completed!")

        .. note::
            Given that you assign the response of ``States.from_enum`` to a class level
            variable on your :ref:`StateMachine` you're good to go, you can use any name to assign
            this response, on this example we used ``_`` to indicate that the name does not matter.
            The variable of type :ref:`States (class)` will be inspected by the metaclass and the
            inner :ref:`State` instances assigned to the state machine.

        Everything else is similar, the ``Enum`` is only used to declare the :ref:`State`
        instances.

        >>> sm = ApprovalMachine()

        >>> sm.pending.is_active
        True

        >>> sm.send("finish")
        Completed!

        >>> sm.completed.is_active
        True

        >>> sm.current_state_value
        2

        Args:
            enum_type: An enumeration containing the states of the machine.
            initial: The initial state of the machine.
            final: A set of final states of the machine.

        Returns:
            A new instance of the :ref:`States (class)`.
        """
        final_set = set(ensure_iterable(final))
        return cls(
            {
                e.name: State(value=e.value, initial=e is initial, final=e in final_set)
                for e in enum_type
            }
        )
