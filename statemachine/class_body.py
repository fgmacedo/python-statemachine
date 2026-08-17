from typing import TYPE_CHECKING
from typing import Any

from .event import Event
from .state import HistoryState
from .state import State
from .states import States
from .transition import Transition
from .transition_list import TransitionList

if TYPE_CHECKING:
    from typing import Protocol

    class ClassBodyReader(Protocol):
        """One method per declaration form that :func:`read` recognizes.

        Adding a form here is what forces every reader to answer for it.
        """

        def on_states(self, states: States) -> None: ...

        def on_history(self, key: str, state: HistoryState) -> None: ...

        def on_state(self, key: str, state: State) -> None: ...

        def on_transitions(self, key: str, transitions: "Transition | TransitionList") -> None: ...

        def on_event(self, key: str, declared: Event) -> None: ...

        def on_decorated(self, key: str, func: Any) -> None: ...

        def on_other(self, key: str, value: Any) -> None: ...


def read(attrs: "dict[str, Any]", reader: "ClassBodyReader") -> None:
    """Dispatch each entry of a statechart class body to ``reader``.

    A statechart is declared in two kinds of class body: a :ref:`StateChart` subclass and a
    nested ``State.Compound`` / ``State.Parallel``. Both accept the same forms, so recognition
    lives here once and each reader supplies only what it does with a form.

    Order is significant: a ``HistoryState`` is a ``State``, and an ``Event`` is a callable
    ``str``, so both would be captured by a later branch.
    """
    for key, value in attrs.items():
        if isinstance(value, States):
            reader.on_states(value)
        elif isinstance(value, HistoryState):
            reader.on_history(key, value)
        elif isinstance(value, State):
            reader.on_state(key, value)
        elif isinstance(value, (Transition, TransitionList)):
            reader.on_transitions(key, value)
        elif isinstance(value, Event):
            reader.on_event(key, value)
        elif getattr(value, "attr_name", None):
            reader.on_decorated(key, value)
        else:
            reader.on_other(key, value)
