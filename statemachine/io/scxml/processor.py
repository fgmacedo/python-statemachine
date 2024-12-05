from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

from .. import StateOptions
from .. import StateWithTransitionsDict
from .. import TransitionDict
from .. import TransitionsDict
from .. import create_machine_class_from_definition
from .actions import create_cond
from .actions import create_datamodel_action_callable
from .actions import create_executable_content
from .parser import parse_scxml
from .schema import Transition


class SCXMLProcessor:
    def __init__(self):
        self.scs = {}
        self.sessions = {}
        self._ioprocessors = {
            "http://www.w3.org/TR/scxml/#SCXMLEventProcessor": self,
            "scxml": self,
        }

    def parse_scxml_file(self, path: Path):
        scxml_content = path.read_text()
        return self.parse_scxml(path.stem, scxml_content)

    def parse_scxml(self, sm_name: str, scxml_content: str):
        definition = parse_scxml(scxml_content)
        self.process_definition(definition, location=sm_name)

    def process_definition(self, definition, location: str):
        states_dict: Dict[str, StateOptions] = {}
        for state_id, state in definition.states.items():
            state_dict = StateWithTransitionsDict()
            if state.initial:
                state_dict["initial"] = True
            if state.final:
                state_dict["final"] = True

            # Process enter actions
            if state.onentry:
                callables = [create_executable_content(content) for content in state.onentry]
                state_dict["enter"] = callables

            # Process exit actions
            if state.onexit:
                callables = [create_executable_content(content) for content in state.onexit]
                state_dict["exit"] = callables

            # Process transitions
            if state.transitions:
                state_dict["on"] = self._process_transitions(state.transitions)

            states_dict[state_id] = state_dict

        extra_data = {}

        # Process datamodel (initial variables)
        if definition.datamodel:
            __init__ = create_datamodel_action_callable(definition.datamodel)
            if __init__:
                extra_data["__init__"] = __init__

        # breakpoint()
        self._add(location, {"states": states_dict, **extra_data})

    def _process_transitions(self, transitions: List[Transition]):
        on_dict: TransitionsDict = {}
        for transition in transitions:
            event = transition.event or None
            if event not in on_dict:
                on_dict[event] = []
            transition_dict: TransitionDict = {"target": transition.target}

            # Process cond
            if transition.cond:
                cond_callable = create_cond(transition.cond, processor=self)
                transition_dict["cond"] = cond_callable

                # Process actions
            if transition.on:
                callable = create_executable_content(transition.on)
                transition_dict["on"] = callable

            on_dict[event].append(transition_dict)
        return on_dict

    def _add(self, location: str, definition: Dict[str, Any]):
        try:
            sc_class = create_machine_class_from_definition(location, **definition)
            self.scs[location] = sc_class
            return sc_class
        except Exception as e:
            raise Exception(
                f"Failed to create state machine class: {e} from definition: {definition}"
            ) from e

    def start(self, **kwargs):
        self.root_cls = next(iter(self.scs.values()))
        self.root = self.root_cls(**kwargs)
        self.sessions[self.root.name] = self.root
        return self.root

    def wrap(self, **kwargs):
        return IOProcessor(self, **kwargs)


class IOProcessor:
    def __init__(self, processor: "SCXMLProcessor", **kwargs):
        self.scxml_processor = processor
        self.machine = kwargs["machine"]

    def __getitem__(self, name: str):
        return self

    @property
    def location(self):
        return self.machine.name
