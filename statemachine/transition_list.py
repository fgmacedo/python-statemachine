from typing import TYPE_CHECKING
from typing import Iterable
from typing import List

from .callbacks import CallbackGroup
from .transition import Transition
from .transition_mixin import AddCallbacksMixin
from .utils import ensure_iterable

if TYPE_CHECKING:
    from .events import Event
    from .state import State


class TransitionList(AddCallbacksMixin):
    """A list-like container of :ref:`transitions` with callback functions."""

    def __init__(self, transitions: "Iterable[Transition] | None" = None):
        """
        Args:
            transitions: An iterable of `Transition` objects.
                Defaults to `None`.

        """
        self.transitions: List[Transition] = list(transitions) if transitions else []

    def __repr__(self):
        """Return a string representation of the :ref:`TransitionList`."""
        return f"{type(self).__name__}({self.transitions!r})"

    def __or__(self, other: "TransitionList | Iterable"):
        """Return a new :ref:`TransitionList` that combines the transitions of this
        :ref:`TransitionList` with another :ref:`TransitionList` or iterable.

        Args:
            other: Another :ref:`TransitionList` or iterable of :ref:`Transition` objects.

        Returns:
            TransitionList: A new :ref:`TransitionList` object that combines the
                transitions of this :ref:`TransitionList` with `other`.

        """
        return TransitionList(self.transitions).add_transitions(other)

    def _on_event_defined(self, event: str, states: List["State"]):
        self.add_event(event)

        for transition in self.transitions:
            transition.source._on_event_defined(event=event, transition=transition, states=states)

    def add_transitions(self, transition: "Transition | TransitionList | Iterable"):
        """Adds one or more transitions to the :ref:`TransitionList` instance.

        Args:
            transition: A sequence of transitions or a :ref:`TransitionList` instance.

        Returns:
            The updated :ref:`TransitionList` instance.
        """
        if isinstance(transition, TransitionList):
            transition = transition.transitions
        transitions = ensure_iterable(transition)

        for transition in transitions:
            assert isinstance(transition, Transition)  # makes mypy happy
            self.transitions.append(transition)

        return self

    def __getitem__(self, index: int) -> "Transition":
        """Returns the :ref:`transition` at the specified ``index``.

        Args:
            index: The index of the transition.

        Returns:
            The :ref:`transition` at the specified index.
        """
        return self.transitions[index]

    def __len__(self):
        """Returns the number of transitions in the :ref:`TransitionList` instance.

        Returns:
            The number of transitions.
        """
        return len(self.transitions)

    def _add_callback(self, callback, grouper: CallbackGroup, is_event=False, **kwargs):
        for transition in self.transitions:
            list_obj = transition._specs.grouper(grouper)
            list_obj._add_unbounded_callback(
                callback,
                is_event=is_event,
                transitions=self,
                **kwargs,
            )
        return callback

    def add_event(self, event: str):
        """
        Adds an event to all transitions in the :ref:`TransitionList` instance.

        Args:
            event: The name of the event to be added.
        """
        for transition in self.transitions:
            transition.add_event(event)

    @property
    def unique_events(self) -> List["Event"]:
        """
        Returns a list of unique event names across all transitions in the :ref:`TransitionList`
        instance.

        Returns:
            A list of unique event names.
        """
        tmp_ordered_unique_events_as_keys_on_dict = {}
        for transition in self.transitions:
            for event in transition.events:
                tmp_ordered_unique_events_as_keys_on_dict[event] = True

        return list(tmp_ordered_unique_events_as_keys_on_dict.keys())
