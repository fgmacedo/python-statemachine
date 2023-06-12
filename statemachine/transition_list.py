from typing import TYPE_CHECKING
from typing import Callable
from typing import Iterable
from typing import List

from .utils import ensure_iterable

if TYPE_CHECKING:
    from .transition import Transition


class TransitionList:
    """A list-like container of :ref:`transitions` with callback functions."""

    def __init__(self, transitions: "Iterable | None" = None):
        """
        Args:
            transitions: An iterable of `Transition` objects.
                Defaults to `None`.

        """
        self.transitions = list(transitions) if transitions else []

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
            self.transitions.append(transition)

        return self

    def __getitem__(self, index: int):
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

    def _add_callback(self, callback, name, is_event=False, **kwargs):
        for transition in self.transitions:
            list_obj = getattr(transition, name)
            list_obj._add_unbounded_callback(
                callback,
                is_event=is_event,
                transitions=self,
                **kwargs,
            )
        return callback

    def __call__(self, f):
        return self._add_callback(f, "on", is_event=True)

    def before(self, f: Callable):
        """Adds a ``before`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``before`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, "before")

    def after(self, f: Callable):
        """Adds a ``after`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``after`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, "after")

    def on(self, f: Callable):
        """Adds a ``on`` :ref:`transition actions` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``on`` :ref:`transition actions` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, "on")

    def cond(self, f: Callable):
        """Adds a ``cond`` :ref:`guards` callback to every :ref:`transition` in the
        :ref:`TransitionList` instance.

        Args:
            f: The ``cond`` :ref:`guards` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, "cond")

    def unless(self, f: Callable):
        """Adds a ``unless`` :ref:`guards` callback with expected value ``False`` to every
        :ref:`transition` in the :ref:`TransitionList` instance.

        Args:
            f: The ``unless`` :ref:`guards` callback function to be added.

        Returns:
            The `f` callable.
        """
        return self._add_callback(f, "cond", expected_value=False)

    def validators(self, f: Callable):
        """Adds a :ref:`validators` callback to the :ref:`TransitionList` instance.

        Args:
            f: The ``validators`` callback function to be added.
        Returns:
            The callback function.

        """
        return self._add_callback(f, "validators")

    def add_event(self, event: str):
        """
        Adds an event to all transitions in the :ref:`TransitionList` instance.

        Args:
            event: The name of the event to be added.
        """
        for transition in self.transitions:
            transition.add_event(event)

    @property
    def unique_events(self) -> List[str]:
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
