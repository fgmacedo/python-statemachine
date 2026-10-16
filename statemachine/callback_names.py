import warnings
from collections.abc import Iterable
from typing import TYPE_CHECKING

from .callbacks import CallbackPriority
from .exceptions import InvalidDefinition
from .graph import iterate_states_and_transitions
from .i18n import _

if TYPE_CHECKING:
    from .state import State

_INIT_PREFIX = "on_init_"


def ambiguous_callback_names(states: "Iterable[State]") -> frozenset[str]:
    """Names that both an event convention (``on_<event>``) and a state convention
    (``on_enter_<state>``, ``on_init_<state>``, ...) bind, such as ``on_init_x`` for an
    event ``init_x`` and a compound state ``x``."""
    event_names: set[str] = set()
    state_names: set[str] = set()
    for visited in iterate_states_and_transitions(states):
        for spec in visited._specs:
            if not spec.is_convention or spec.priority != CallbackPriority.NAMING:
                continue
            if spec.cond is None:
                state_names.add(spec.func)
            else:
                event_names.add(spec.func)
    return frozenset(event_names & state_names)


def check_callback_names(owner: str, names: Iterable[str], stacklevel: int):
    """Reject or deprecate the ambiguous callback names that ``owner`` defines.

    ``stacklevel`` counts from the caller, as in :func:`warnings.warn`."""
    names = sorted(names)
    if not names:
        return

    rejected = [name for name in names if name.startswith(_INIT_PREFIX)]
    if rejected:
        raise InvalidDefinition(
            _(
                "{owner} defines {names}, bound both to an event and to the initial "
                "transition of a compound state. Rename the event or the method."
            ).format(owner=owner, names=", ".join(rejected))
        )

    warnings.warn(
        _(
            "{owner} defines {names}, bound both to an event and to a state callback, so "
            "it runs for both. This will raise InvalidDefinition in 4.0. "
            "Rename the event or the method."
        ).format(owner=owner, names=", ".join(names)),
        DeprecationWarning,
        stacklevel=stacklevel + 1,
    )
