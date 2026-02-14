import warnings
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from . import registry
from .callbacks import CallbackGroup
from .callbacks import CallbackPriority
from .callbacks import CallbackSpecList
from .event import Event
from .exceptions import InvalidDefinition
from .graph import disconnected_states
from .graph import iterate_states
from .graph import iterate_states_and_transitions
from .graph import states_without_path_to_final_states
from .i18n import _
from .state import State
from .states import States
from .transition import Transition
from .transition_list import TransitionList


class StateMachineMetaclass(type):
    "Metaclass for constructing StateMachine classes"

    validate_disconnected_states: bool = True
    """If `True`, the state machine will validate that there are no unreachable states."""

    def __init__(
        cls,
        name: str,
        bases: Tuple[type],
        attrs: Dict[str, Any],
        strict_states: bool = False,
    ) -> None:
        super().__init__(name, bases, attrs)
        registry.register(cls)
        cls.name = cls.__name__
        cls.id = cls.name.lower()
        # TODO: Experiment with the IDEA of a root state
        # cls.root = State(id=cls.id, name=cls.name)
        cls.states: States = States()
        cls.states_map: Dict[Any, State] = {}
        """Map of ``state.value`` to the corresponding :ref:`state`."""

        cls._abstract = True
        cls._strict_states = strict_states
        cls._events: Dict[Event, None] = {}  # used Dict to preserve order and avoid duplicates
        cls._protected_attrs: set = set()
        cls._events_to_update: Dict[Event, Event | None] = {}
        cls._specs = CallbackSpecList()
        cls.prepare = cls._specs.grouper(CallbackGroup.PREPARE).add(
            "prepare_event", priority=CallbackPriority.GENERIC, is_convention=True
        )
        cls.add_inherited(bases)
        cls.add_from_attributes(attrs)
        cls._unpack_builders_callbacks()
        cls._update_event_references()

        if not cls.states:
            return

        cls._initials_by_document_order(list(cls.states), parent=None)

        initials = [s for s in cls.states if s.initial]
        parallels = [s.id for s in cls.states if s.parallel]
        root_only_has_parallels = len(cls.states) == len(parallels)

        if len(initials) != 1 and not root_only_has_parallels:
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "Your currently have these: {0}"
                ).format(", ".join(s.id for s in initials))
            )

        if initials:
            cls.initial_state = initials[0]
        else:  # pragma: no cover
            cls.initial_state = None

        cls.final_states: List[State] = [state for state in cls.states if state.final]

        cls._check()
        cls._setup()

    if TYPE_CHECKING:
        """Makes mypy happy with dynamic created attributes"""

        def __getattr__(self, attribute: str) -> Any: ...

    def _initials_by_document_order(  # noqa: C901
        cls, states: List[State], parent: "State | None" = None, order: int = 1
    ):
        """Set initial state by document order if no explicit initial state is set"""
        initials: List[State] = []
        for s in states:
            s.document_order = order
            order += 1
            if s.states:
                cls._initials_by_document_order(s.states, s, order)
            if s.initial:
                initials.append(s)

        if not initials and states:
            initial = states[0]
            initial._initial = True
            initials.append(initial)

        if not parent:
            return

        # If parent already has a multi-target initial transition (e.g., from SCXML initial
        # attribute targeting multiple parallel regions), don't create default initial transitions.
        if any(t for t in parent.transitions if t.initial and len(t.targets) > 1):
            return

        for initial in initials:
            if not any(t for t in parent.transitions if t.initial and t.target == initial):
                parent.to(initial, initial=True)

        if not parent.parallel:
            return

        for state in states:
            state._initial = True
            if not any(t for t in parent.transitions if t.initial and t.target == state):
                parent.to(state, initial=True)  # pragma: no cover

    def _unpack_builders_callbacks(cls):
        callbacks = {}
        for state in iterate_states(cls.states):
            if state._callbacks:
                callbacks.update(state._callbacks)
                del state._callbacks
        for key, value in callbacks.items():
            setattr(cls, key, value)

    def _check(cls):
        has_states = bool(cls.states)
        cls._abstract = not has_states

        # do not validate the base abstract classes
        if cls._abstract:  # pragma: no cover
            return

        cls._check_initial_state()
        cls._check_final_states()
        cls._check_disconnected_state()
        cls._check_trap_states()
        cls._check_reachable_final_states()

    def _check_initial_state(cls):
        initials = [s for s in cls.states if s.initial]
        if len(initials) != 1:  # pragma: no cover
            raise InvalidDefinition(
                _(
                    "There should be one and only one initial state. "
                    "You currently have these: {!r}"
                ).format([s.id for s in initials])
            )
        # TODO: Check if this is still needed
        # if not initials[0].transitions.transitions:
        #     raise InvalidDefinition(_("There are no transitions."))

    def _check_final_states(cls):
        final_state_with_invalid_transitions = [
            state for state in cls.final_states if state.transitions
        ]

        if final_state_with_invalid_transitions:
            raise InvalidDefinition(
                _("Cannot declare transitions from final state. Invalid state(s): {}").format(
                    [s.id for s in final_state_with_invalid_transitions]
                )
            )

    def _check_trap_states(cls):
        trap_states = [s for s in cls.states if not s.final and not s.transitions]
        if trap_states:
            message = _(
                "All non-final states should have at least one outgoing transition. "
                "These states have no outgoing transition: {!r}"
            ).format([s.id for s in trap_states])
            if cls._strict_states:
                raise InvalidDefinition(message)
            else:
                warnings.warn(message, UserWarning, stacklevel=4)

    def _check_reachable_final_states(cls):
        if not any(s.final for s in cls.states):
            return  # No need to check final reachability
        disconnected_states = list(states_without_path_to_final_states(cls.states))
        if disconnected_states:
            message = _(
                "All non-final states should have at least one path to a final state. "
                "These states have no path to a final state: {!r}"
            ).format([s.id for s in disconnected_states])
            if cls._strict_states:
                raise InvalidDefinition(message)
            else:
                warnings.warn(message, UserWarning, stacklevel=1)

    def _check_disconnected_state(cls):
        if not cls.validate_disconnected_states:
            return
        assert cls.initial_state
        states = disconnected_states(cls.initial_state, set(cls.states_map.values()))
        if states:
            raise InvalidDefinition(
                _(
                    "There are unreachable states. "
                    "The statemachine graph should have a single component. "
                    "Disconnected states: {}"
                ).format([s.id for s in states])
            )

    def _setup(cls):
        for visited in iterate_states_and_transitions(cls.states):
            visited._setup()

        cls._protected_attrs = {
            "_abstract",
            "model",
            "state_field",
            "start_value",
            "initial_state",
            "final_states",
            "states",
            "_events",
            "states_map",
            "send",
        } | {s.id for s in cls.states}

    def add_inherited(cls, bases):
        for base in bases:
            for state in getattr(base, "states", []):
                cls.add_state(state.id, state)

            events = getattr(base, "_events", {})
            for event in events:
                cls.add_event(event=Event(id=event.id, name=event.name))

    def add_from_attributes(cls, attrs):  # noqa: C901
        for key, value in attrs.items():
            if isinstance(value, States):
                cls._add_states_from_dict(value)
            if isinstance(value, State):
                cls.add_state(key, value)
            elif isinstance(value, (Transition, TransitionList)):
                event_id = key
                if key.startswith("error_"):
                    event_id = f"{key} {key.replace('_', '.')}"
                elif key.startswith("done_state_"):
                    suffix = key[len("done_state_") :]
                    event_id = f"{key} done.state.{suffix}"
                cls.add_event(event=Event(transitions=value, id=event_id, name=key))
            elif isinstance(value, (Event,)):
                if value._has_real_id:
                    event_id = value.id
                elif key.startswith("error_"):
                    event_id = f"{key} {key.replace('_', '.')}"
                elif key.startswith("done_state_"):
                    suffix = key[len("done_state_") :]
                    event_id = f"{key} done.state.{suffix}"
                else:
                    event_id = key
                new_event = Event(
                    transitions=value._transitions,
                    id=event_id,
                    name=value.name,
                )
                cls.add_event(event=new_event, old_event=value)
                # Ensure the event is accessible by the Python attribute name
                if event_id != key:
                    setattr(cls, key, new_event)
            elif getattr(value, "attr_name", None):
                cls._add_unbounded_callback(key, value)

    def _add_states_from_dict(cls, states):
        for state_id, state in states.items():
            cls.add_state(state_id, state)

    def _add_unbounded_callback(cls, attr_name, func):
        # if func is an event, the `attr_name` will be replaced by an event trigger,
        # so we'll also give the ``func`` a new unique name to be used by the callback
        # machinery that is stored at ``func.attr_name``
        setattr(cls, func.attr_name, func)
        if func.is_event:
            cls.add_event(event=Event(func._transitions, id=attr_name, name=attr_name))

    def add_state(cls, id, state: State):
        state._set_id(id)
        cls.states_map[state.value] = state
        if not state.parent:
            cls.states.append(state)
            if not hasattr(cls, id):
                setattr(cls, id, state)

        # also register all events associated directly with transitions
        for event in state.transitions.unique_events:
            cls.add_event(event)

        for substate in state.states:
            cls.add_state(substate.id, substate)

    def add_event(
        cls,
        event: Event,
        old_event: "Event | None" = None,
    ):
        if not event._has_real_id:
            if event not in cls._events_to_update:
                cls._events_to_update[event] = None
            return

        transitions = event._transitions
        if transitions is not None:
            transitions._on_event_defined(event=event, states=list(cls.states))

        if event not in cls._events:
            cls._events[event] = None
            setattr(cls, event.id, event)

        if old_event is not None:
            cls._events_to_update[old_event] = event

        return cls._events[event]

    def _update_event_references(cls):
        for old_event, new_event in cls._events_to_update.items():
            for state in cls.states:
                for transition in state.transitions:
                    if transition._events.match(old_event):
                        if new_event is None:
                            raise InvalidDefinition(
                                _("An event in the '{}' has no id.").format(transition)
                            )
                        transition.events._replace(old_event, new_event)

        cls._events_to_update = {}

    @property
    def events(self):
        return list(self._events)
