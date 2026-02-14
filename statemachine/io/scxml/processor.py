import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from ...event import Event
from ...exceptions import InvalidDefinition
from ...statemachine import StateChart
from .. import HistoryDefinition
from .. import StateDefinition
from .. import TransitionDict
from .. import TransitionsList
from .. import create_machine_class_from_definition
from .actions import Cond
from .actions import DoneDataCallable
from .actions import EventDataWrapper
from .actions import ExecuteBlock
from .actions import create_datamodel_action_callable
from .parser import parse_scxml
from .schema import HistoryState
from .schema import State
from .schema import Transition


@contextmanager
def temporary_directory(new_current_dir):
    original_dir = os.getcwd()
    try:
        os.chdir(new_current_dir)
        yield
    finally:
        os.chdir(original_dir)


class IOProcessor:
    def __init__(self, processor: "SCXMLProcessor", machine: StateChart):
        self.scxml_processor = processor
        self.machine = machine

    def __getitem__(self, name: str):
        return self

    @property
    def location(self):
        return self.machine.name

    def get(self, name: str):
        return getattr(self, name)


@dataclass
class SessionData:
    machine: StateChart
    processor: IOProcessor
    first_event_raised: bool = False

    def __post_init__(self):
        self.session_id = f"{self.machine.name}:{id(self.machine)}"


class SCXMLProcessor:
    def __init__(self):
        self.scs = {}
        self.sessions: Dict[str, SessionData] = {}
        self._ioprocessors = {
            "http://www.w3.org/TR/scxml/#SCXMLEventProcessor": self,
            "scxml": self,
        }

    def parse_scxml_file(self, path: Path):
        scxml_content = path.read_text()
        with temporary_directory(path.parent):
            return self.parse_scxml(path.stem, scxml_content)

    def parse_scxml(self, sm_name: str, scxml_content: str):
        definition = parse_scxml(scxml_content)
        self.process_definition(definition, location=definition.name or sm_name)

    def process_definition(self, definition, location: str):
        states_dict = self._process_states(definition.states)

        # Process datamodel (initial variables)
        if definition.datamodel:
            datamodel = create_datamodel_action_callable(definition.datamodel)
            if datamodel:
                try:
                    initial_state = next(s for s in iter(states_dict.values()) if s.get("initial"))
                except StopIteration:
                    # If there's no explicit initial state, use the first one
                    initial_state = next(iter(states_dict.values()))

                if "enter" not in initial_state:
                    initial_state["enter"] = []
                if isinstance(initial_state["enter"], list):
                    initial_state["enter"].insert(0, datamodel)

        self._add(
            location,
            {
                "states": states_dict,
                "prepare_event": self._prepare_event,
                "validate_disconnected_states": False,
                "start_configuration_values": list(definition.initial_states),
            },
        )

    def _prepare_event(self, *args, event: Event, **kwargs):
        machine = kwargs["machine"]
        session_data = self._get_session(machine)

        if not session_data.first_event_raised and event and event != "__initial__":
            session_data.first_event_raised = True

        _event: "EventDataWrapper | None" = None
        if session_data.first_event_raised:
            _event = EventDataWrapper(kwargs["event_data"])

        return {
            "_name": machine.name,
            "_sessionid": session_data.session_id,
            "_ioprocessors": session_data.processor,
            "_event": _event,
        }

    def _get_session(self, machine: StateChart):
        if machine.name not in self.sessions:
            self.sessions[machine.name] = SessionData(
                processor=IOProcessor(self, machine=machine), machine=machine
            )
        return self.sessions[machine.name]

    def _process_history(self, history: Dict[str, HistoryState]) -> Dict[str, HistoryDefinition]:
        states_dict: Dict[str, HistoryDefinition] = {}
        for state_id, state in history.items():
            state_dict = HistoryDefinition()

            state_dict["deep"] = state.deep

            # Process transitions
            if state.transitions:
                state_dict["transitions"] = self._process_transitions(state.transitions)

            states_dict[state_id] = state_dict

        return states_dict

    def _process_states(self, states: Dict[str, State]) -> Dict[str, StateDefinition]:
        states_dict: Dict[str, StateDefinition] = {}
        for state_id, state in states.items():
            states_dict[state_id] = self._process_state(state)
        return states_dict

    def _process_state(self, state: State) -> StateDefinition:
        state_dict = StateDefinition()
        if state.initial:
            state_dict["initial"] = True
        if state.final:
            state_dict["final"] = True
        if state.parallel:
            state_dict["parallel"] = True

        # Process enter actions
        enter_callables: list = [
            ExecuteBlock(content) for content in state.onentry if not content.is_empty
        ]
        if enter_callables:
            state_dict["enter"] = enter_callables
        if state.final and state.donedata:
            state_dict["donedata"] = DoneDataCallable(state.donedata)

        # Process exit actions
        if state.onexit:
            callables = [ExecuteBlock(content) for content in state.onexit if not content.is_empty]
            state_dict["exit"] = callables

        # Process transitions
        if state.transitions:
            state_dict["transitions"] = self._process_transitions(state.transitions)

        if state.states:
            state_dict["states"] = self._process_states(state.states)

        if state.history:
            state_dict["history"] = self._process_history(state.history)

        return state_dict

    def _process_transitions(self, transitions: List[Transition]):
        result: TransitionsList = []
        for transition in transitions:
            event = transition.event or None
            transition_dict: TransitionDict = {
                "event": event,
                "target": transition.target,
                "internal": transition.internal,
                "initial": transition.initial,
            }

            # Process cond
            if transition.cond:
                cond_callable = Cond.create(transition.cond, processor=self)
                if cond_callable is not None:
                    transition_dict["cond"] = cond_callable

                # Process actions
            if transition.on and not transition.on.is_empty:
                transition_dict["on"] = ExecuteBlock(transition.on)

            result.append(transition_dict)
        return result

    def _add(self, location: str, definition: Dict[str, Any]):
        try:
            sc_class = create_machine_class_from_definition(location, **definition)
            self.scs[location] = sc_class
            return sc_class
        except Exception as e:
            raise InvalidDefinition(
                f"Failed to create state machine class: {e} from definition: {definition}"
            ) from e

    def start(self, **kwargs):
        self.root_cls = next(iter(self.scs.values()))
        self.root = self.root_cls(**kwargs)
        return self.root
