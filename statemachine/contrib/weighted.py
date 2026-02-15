import random
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

from statemachine.callbacks import CallbackPriority
from statemachine.transition_list import TransitionList

if TYPE_CHECKING:
    from statemachine.state import State


class _WeightedGroup:
    """Holds weights and a shared random.Random instance for a group of weighted transitions.

    When the first transition's cond (index 0) is evaluated, it rolls the dice and caches
    the selected index. Subsequent conds check against the cache.
    """

    def __init__(self, weights: List[float], seed: "int | float | str | None" = None):
        self.weights = weights
        self.rng = random.Random(seed)
        self._selected: "int | None" = None
        self._population = list(range(len(weights)))

    def select(self) -> int:
        """Roll the dice and cache the selected index."""
        self._selected = self.rng.choices(self._population, weights=self.weights, k=1)[0]
        return self._selected

    @property
    def selected(self) -> "int | None":
        return self._selected


def _make_weighted_cond(index: int, group: _WeightedGroup, weight: float, total_weight: float):
    """Create a weighted condition callable for a specific transition index.

    Returns a function that, when called, returns True only for the selected weighted
    transition. Index 0 rolls the dice; other indices check against the cached selection.
    """
    pct = weight / total_weight * 100

    def weighted_cond() -> bool:
        if index == 0:
            selected = group.select()
        elif group.selected is None:
            selected = group.select()
        else:
            selected = group.selected
        return selected == index

    weighted_cond.__name__ = f"weight={weight} ({pct:.0f}%)"
    weighted_cond.__qualname__ = f"_weighted_cond_{index}_{id(group)}"
    return weighted_cond


# Type alias for a weighted destination:
#   (target, weight)  or  (target, weight, kwargs_dict)
_WeightedDest = Union[
    Tuple["State", Union[int, float]],
    Tuple["State", Union[int, float], Dict[str, Any]],
]


def to(target: "State", weight: "int | float", **kwargs: Any) -> _WeightedDest:
    """Build a weighted destination with transition keyword arguments.

    Syntactic sugar that returns a ``(target, weight, kwargs)`` tuple, allowing
    transition options (``cond``, ``unless``, ``before``, ``on``, ``after``, …) to be
    passed as natural keyword arguments instead of a dict.

    For simple cases without extra options, a plain ``(target, weight)`` tuple works
    just as well — ``to()`` is only needed when you want to add transition kwargs.

    Args:
        target: The destination state.
        weight: A positive number representing the relative weight.
        **kwargs: Keyword arguments forwarded to ``source.to(target, **kwargs)``.

    Returns:
        A ``(target, weight, kwargs)`` tuple accepted by :func:`weighted_transitions`.

    Example::

        move = weighted_transitions(
            standing,
            to(walk, 70),
            to(run, 30, cond="has_energy", on="start_running"),
            seed=42,
        )

    """
    return (target, weight, kwargs)


def _validate_dest(i: int, item: Any) -> "Tuple[State, float, Dict[str, Any]]":
    """Validate and normalize a single ``(target, weight[, kwargs])`` tuple."""
    from statemachine.state import State

    if not isinstance(item, tuple) or len(item) not in (2, 3):
        raise TypeError(
            f"Destination {i} must be a (target_state, weight) or "
            f"(target_state, weight, kwargs) tuple, got {type(item).__name__}"
        )

    if len(item) == 2:
        target, weight = item
        kwargs: Dict[str, Any] = {}
    else:
        target, weight, kwargs = item
        if not isinstance(kwargs, dict):
            raise TypeError(
                f"Destination {i}: third element must be a dict of "
                f"transition kwargs, got {type(kwargs).__name__}"
            )

    if not isinstance(target, State):
        raise TypeError(
            f"Destination {i}: first element must be a State, got {type(target).__name__}"
        )

    if not isinstance(weight, (int, float)):
        raise TypeError(
            f"Destination {i}: weight must be a positive number, got {type(weight).__name__}"
        )
    if weight <= 0:
        raise ValueError(f"Destination {i}: weight must be positive, got {weight}")

    return target, float(weight), kwargs


def weighted_transitions(
    source: "State",
    *destinations: _WeightedDest,
    seed: "int | float | str | None" = None,
) -> TransitionList:
    """Create a :ref:`TransitionList` where transitions are selected probabilistically
    based on weights.

    Takes a ``source`` state and one or more ``(target, weight)`` tuples. For simple
    cases a plain tuple is enough. When you need transition options (``cond``, ``on``,
    etc.), use the :func:`to` helper to pass them as keyword arguments::

        move = weighted_transitions(
            standing,
            (walk, 70),                                  # plain tuple
            to(run, 30, cond="has_energy", on="sprint"), # with kwargs
            seed=42,
        )

    The returned :ref:`TransitionList` can be assigned to a class attribute just like
    any other event definition. At runtime, the engine evaluates the weighted conditions
    and selects exactly one transition per event dispatch according to the weight
    distribution.

    Args:
        source: The source state for all transitions.
        *destinations: ``(target, weight)`` tuples or :func:`to` calls.
        seed: Optional seed for the random number generator (for reproducibility).

    Returns:
        A :ref:`TransitionList` combining all transitions with weighted conditions.

    """
    from statemachine.state import State

    if not isinstance(source, State):
        raise TypeError(f"First argument must be a source State, got {type(source).__name__}")

    if not destinations:
        raise ValueError(
            "weighted_transitions() requires at least one (target, weight) destination"
        )

    validated = [_validate_dest(i, item) for i, item in enumerate(destinations)]

    weights = [w for _, w, _ in validated]
    total_weight = sum(weights)
    group = _WeightedGroup(weights, seed=seed)

    result = TransitionList()
    for index, (target, weight, kwargs) in enumerate(validated):
        trans = source.to(target, **kwargs)
        cond_fn = _make_weighted_cond(index, group, weight, total_weight)
        for transition in trans.transitions:
            transition.cond.add(cond_fn, priority=CallbackPriority.GENERIC, expected_value=True)
        result.add_transitions(trans)

    return result
