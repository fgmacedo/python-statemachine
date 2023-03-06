from enum import Enum
from typing import Dict  # deprecated since 3.9: https://peps.python.org/pep-0585/
from typing import Type

from .state import State
from .utils import ensure_iterable

EnumType = Type[Enum]


class States:
    """
    A class representing a collection of :ref:`State` objects.
    """

    def __init__(self, states: Dict) -> None:
        """
        Initializes a new instance of the States class.

        Args:
            states (dict): A dictionary containing the states of the machine.

        Returns:
            None.
        """
        self._states = states
        for state_id, state in states.items():
            setattr(self, state_id, state)

    def items(self):
        """
        Returns the items in the _states dictionary.

        Args:
            None.

        Returns:
            A view object of the items in the _states dictionary.
        """
        return self._states.items()

    @classmethod
    def from_enum(cls, enum_type: EnumType, initial: Enum, final=None):
        """
        Creates a new instance of the ``States`` class from an enumeration.

        Args:
            enum_type: An enumeration containing the states of the machine.
            initial: The initial state of the machine.
            final: A set of final states of the machine.

        Returns:
            A new instance of the States class.
        """
        final = set(ensure_iterable(final))
        return cls(
            {
                e.name: State(value=e.value, initial=e is initial, final=e in final)
                for e in enum_type
            }
        )
