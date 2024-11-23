from dataclasses import dataclass
from dataclasses import field

from statemachine import State
from statemachine import StateMachine
from statemachine.event import Event

"""
Test cases as defined by W3C SCXML Test Suite

- https://www.w3.org/Voice/2013/scxml-irp/
- https://alexzhornyak.github.io/SCXML-tutorial/Tests/ecma/W3C/Mandatory/Auto/report__USCXML_2_0_0___msvc2015_32bit__Win7_1.html
- https://github.com/alexzhornyak/PyBlendSCXML/tree/master/w3c_tests
- https://github.com/jbeard4/SCION/wiki/Pseudocode-for-SCION-step-algorithm

"""  # noqa: E501


@dataclass(frozen=True, unsafe_hash=True)
class DebugListener:
    events: list = field(default_factory=list)

    def on_transition(self, event: Event, source: State, target: State):
        self.events.append(f"{source and source.id} --({event and event.id})--> {target.id}")


def test_usecase(testcase_path, sm_class):
    # from statemachine.contrib.diagram import DotGraphMachine

    # DotGraphMachine(sm_class).get_graph().write_png(
    #     testcase_path.parent / f"{testcase_path.stem}.png"
    # )
    debug = DebugListener()
    sm = sm_class(listeners=[debug])
    assert isinstance(sm, StateMachine)
    assert sm.current_state.id == "pass", debug
