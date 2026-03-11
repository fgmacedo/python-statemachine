from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Mapping
from typing import MutableSet

from .exceptions import InvalidStateValue
from .i18n import _
from .orderedset import OrderedSet

_SENTINEL = object()

if TYPE_CHECKING:
    from .state import State


class Configuration:
    """Encapsulates the dual representation of the active state configuration.

    Internally, ``current_state_value`` is either a scalar (single active state)
    or an ``OrderedSet`` (parallel regions).  This class hides that detail behind
    a uniform interface for reading, mutating, and caching the resolved
    ``OrderedSet[State]``.
    """

    __slots__ = (
        "_instance_states",
        "_model",
        "_state_field",
        "_states_map",
        "_cached",
        "_cached_value",
    )

    def __init__(
        self,
        instance_states: "Mapping[str, State]",
        model: Any,
        state_field: str,
        states_map: "Dict[Any, State]",
    ):
        self._instance_states = instance_states
        self._model = model
        self._state_field = state_field
        self._states_map = states_map
        self._cached: "OrderedSet[State] | None" = None
        self._cached_value: Any = _SENTINEL

    # -- Raw value (persisted on the model) ------------------------------------

    @property
    def value(self) -> Any:
        """The raw state value stored on the model (scalar or ``OrderedSet``)."""
        return getattr(self._model, self._state_field, None)

    @value.setter
    def value(self, val: Any):
        self._invalidate()
        if val is not None and not isinstance(val, MutableSet) and val not in self._states_map:
            raise InvalidStateValue(val)
        setattr(self._model, self._state_field, val)

    @property
    def values(self) -> OrderedSet[Any]:
        """The set of raw state values currently active."""
        v = self.value
        if isinstance(v, OrderedSet):
            return v
        return OrderedSet([v])

    # -- Resolved states -------------------------------------------------------

    @property
    def states(self) -> "OrderedSet[State]":
        """The set of currently active :class:`State` instances (cached)."""
        csv = self.value
        if self._cached is not None and self._cached_value is csv:
            return self._cached
        if csv is None:
            return OrderedSet()

        instance_states = self._instance_states
        if not isinstance(csv, MutableSet):
            result = OrderedSet([instance_states[self._states_map[csv].id]])
        else:
            result = OrderedSet([instance_states[self._states_map[v].id] for v in csv])

        self._cached = result
        self._cached_value = csv
        return result

    @states.setter
    def states(self, new_configuration: "OrderedSet[State]"):
        if len(new_configuration) == 0:
            self.value = None
        elif len(new_configuration) == 1:
            self.value = next(iter(new_configuration)).value
        else:
            self.value = OrderedSet(s.value for s in new_configuration)

    # -- Incremental mutation (used by the engine) -----------------------------

    def add(self, state: "State"):
        """Add *state* to the configuration, maintaining the dual representation."""
        csv = self.value
        if csv is None:
            self.value = state.value
        elif isinstance(csv, MutableSet):
            new = OrderedSet(csv)
            new.add(state.value)
            self.value = new
        else:
            self.value = OrderedSet([csv, state.value])

    def discard(self, state: "State"):
        """Remove *state* from the configuration, normalizing back to scalar."""
        csv = self.value
        if isinstance(csv, MutableSet):
            new = OrderedSet(v for v in csv if v != state.value)
            if len(new) == 0:
                self.value = None
            elif len(new) == 1:
                self.value = next(iter(new))
            else:
                self.value = new
        elif csv == state.value:
            self.value = None

    # -- Deprecated v2 compat --------------------------------------------------

    @property
    def current_state(self) -> "State | OrderedSet[State]":
        """Resolve the current state with validation.

        Unlike ``states`` (which returns an empty set for ``None``), this
        raises ``InvalidStateValue`` when the value is ``None`` or not
        found in ``states_map`` — matching the v2 ``current_state`` contract.
        """
        csv = self.value
        if csv is None:
            raise InvalidStateValue(
                csv,
                _(
                    "There's no current state set. In async code, "
                    "did you activate the initial state? "
                    "(e.g., `await sm.activate_initial_state()`)"
                ),
            )
        try:
            config = self.states
            if len(config) == 1:
                return next(iter(config))
            return config
        except KeyError as err:
            raise InvalidStateValue(csv) from err

    # -- Internal --------------------------------------------------------------

    def _invalidate(self):
        self._cached = None
        self._cached_value = _SENTINEL
