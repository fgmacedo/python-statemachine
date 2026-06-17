from collections.abc import Mapping
from collections.abc import MutableSet
from typing import TYPE_CHECKING
from typing import Any

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
        instance_states: "Mapping[Any, State]",
        model: Any,
        state_field: str,
        states_map: "dict[Any, State]",
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
        if val is None:
            self._write_to_model(OrderedSet())
        elif isinstance(val, MutableSet):
            self._write_to_model(OrderedSet(val) if not isinstance(val, OrderedSet) else val)
        else:
            self._write_to_model(OrderedSet([val]))

    @property
    def values(self) -> OrderedSet[Any]:
        """The set of raw state values currently active."""
        return self._read_from_model()

    # -- Resolved states -------------------------------------------------------

    @property
    def states(self) -> "OrderedSet[State]":
        """The set of currently active :class:`State` instances (cached)."""
        raw = self.value
        # Snapshot the cache fields locally — another thread may call
        # ``_invalidate()`` between the freshness check and the return,
        # so reading ``self._cached`` twice would risk returning ``None``.
        cached = self._cached
        cached_value = self._cached_value
        if cached is not None and cached_value is raw:
            return cached
        if raw is None:
            return OrderedSet()

        # Normalize inline (avoid second getattr via _read_from_model)
        values = raw if isinstance(raw, MutableSet) else (raw,)
        result = OrderedSet(self._instance_states[v] for v in values)
        self._cached = result
        self._cached_value = raw
        return result

    @states.setter
    def states(self, new_configuration: "OrderedSet[State]"):
        self._write_to_model(OrderedSet(s.value for s in new_configuration))

    # -- Incremental mutation (used by the engine) -----------------------------

    def add(self, state: "State"):
        """Add *state* to the configuration (copy-on-write for thread safety)."""
        # Copy so we never mutate the OrderedSet still held by concurrent
        # readers or by the cache identity check. ``_read_from_model`` may
        # return the same ref stored on the model.
        values = OrderedSet(self._read_from_model())
        values.add(state.value)
        self._write_to_model(values)

    def discard(self, state: "State"):
        """Remove *state* from the configuration (copy-on-write for thread safety)."""
        values = OrderedSet(self._read_from_model())
        values.discard(state.value)
        self._write_to_model(values)

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

    # -- Internal: model boundary ----------------------------------------------

    def _read_from_model(self) -> OrderedSet:
        """Normalize: model value → always ``OrderedSet``."""
        raw = self.value
        if raw is None:
            return OrderedSet()
        if isinstance(raw, OrderedSet):
            return raw
        if isinstance(raw, MutableSet):
            return OrderedSet(raw)
        return OrderedSet([raw])

    def _write_to_model(self, values: OrderedSet):
        """Denormalize: ``OrderedSet`` → ``None | scalar | OrderedSet`` for model."""
        self._invalidate()
        if len(values) == 0:
            raw = None
        elif len(values) == 1:
            raw = next(iter(values))
        else:
            raw = values
        if raw is not None and not isinstance(raw, MutableSet) and raw not in self._states_map:
            raise InvalidStateValue(raw)
        setattr(self._model, self._state_field, raw)

    def _invalidate(self):
        self._cached = None
        self._cached_value = _SENTINEL
