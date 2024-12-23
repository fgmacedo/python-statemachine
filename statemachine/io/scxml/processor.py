import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from ...event import Event
from ...exceptions import InvalidDefinition
from ...statemachine import StateMachine
from .. import StateDefinition
from .. import TransitionDict
from .. import TransitionsDict
from .. import create_machine_class_from_definition
from .actions import Cond
from .actions import EventDataWrapper
from .actions import ExecuteBlock
from .actions import create_datamodel_action_callable
from .parser import parse_scxml
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
    def __init__(self, processor: "SCXMLProcessor", machine: StateMachine):
        self.scxml_processor = processor
        self.machine = machine

    def __getitem__(self, name: str):
        return self

    @property
    def location(self):
        return self.machine.name


@dataclass
class SessionData:
    machine: StateMachine
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
            },
        )

    def _prepare_event(self, *args, event: Event, **kwargs):
        machine = kwargs["machine"]
        machine_weakref = getattr(machine, "__weakref__", None)
        if machine_weakref:
            machine = machine_weakref()

        session_data = self._get_session(machine)

        extra_params = {}
        if not session_data.first_event_raised and event and not event == "__initial__":
            session_data.first_event_raised = True

        if session_data.first_event_raised:
            extra_params = {"_event": EventDataWrapper(kwargs["event_data"])}

        return {
            "_name": machine.name,
            "_sessionid": session_data.session_id,
            "_ioprocessors": session_data.processor,
            **extra_params,
        }

    def _get_session(self, machine: StateMachine):
        if machine.name not in self.sessions:
            self.sessions[machine.name] = SessionData(
                processor=IOProcessor(self, machine=machine), machine=machine
            )
        return self.sessions[machine.name]

    def _process_states(self, states: Dict[str, State]) -> Dict[str, StateDefinition]:
        states_dict: Dict[str, StateDefinition] = {}
        for state_id, state in states.items():
            state_dict = StateDefinition()
            if state.initial:
                state_dict["initial"] = True
            if state.final:
                state_dict["final"] = True
            if state.parallel:
                state_dict["parallel"] = True

            # Process enter actions
            if state.onentry:
                callables = [
                    ExecuteBlock(content) for content in state.onentry if not content.is_empty
                ]
                state_dict["enter"] = callables

            # Process exit actions
            if state.onexit:
                callables = [
                    ExecuteBlock(content) for content in state.onexit if not content.is_empty
                ]
                state_dict["exit"] = callables

            # Process transitions
            if state.transitions:
                state_dict["on"] = self._process_transitions(state.transitions)

            states_dict[state_id] = state_dict

            if state.states:
                state_dict["states"] = self._process_states(state.states)

        return states_dict

    def _process_transitions(self, transitions: List[Transition]):
        on_dict: TransitionsDict = {}
        for transition in transitions:
            event = transition.event or None
            if event not in on_dict:
                on_dict[event] = []
            transition_dict: TransitionDict = {
                "target": transition.target,
                "internal": transition.internal,
                "initial": transition.initial,
            }

            # Process cond
            if transition.cond:
                cond_callable = Cond.create(transition.cond, processor=self)
                transition_dict["cond"] = cond_callable

                # Process actions
            if transition.on and not transition.on.is_empty:
                callable = ExecuteBlock(transition.on)
                transition_dict["on"] = callable

            on_dict[event].append(transition_dict)
        return on_dict

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
        kwargs["allow_event_without_transition"] = True
        kwargs["enable_self_transition_entries"] = True
        self.root_cls = next(iter(self.scs.values()))
        self.root = self.root_cls(**kwargs)
        return self.root
