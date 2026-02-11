import pytest
from statemachine.io.scxml.processor import SCXMLProcessor
from statemachine.state import State

from statemachine import StateChart

"""
The <initial> specifies a transition that specifies the default child initial states.

The problem is that the transition must occur, and the state itself is not marked
as `initial` in the model.

"""

MICROWAVE_SCXML = """
<scxml initial="unplugged">
  <state id="unplugged">
    <transition event="plug-in" target="plugged-in"/>
  </state>

  <state id="plugged-in">
    <initial>
      <transition target="idle"/>
    </initial>
    <state id="idle">
      <transition event="start" target="cooking"/>
    </state>
    <state id="cooking">
      <transition event="stop" target="idle"/>
    </state>
    <transition event="unplug" target="unplugged"/>
  </state>
</scxml>
"""


@pytest.mark.scxml()
def test_microwave_scxml():
    # from statemachine.contrib.diagram import DotGraphMachine

    processor = SCXMLProcessor()
    processor.parse_scxml("microwave", MICROWAVE_SCXML)
    sm = processor.start()
    # DotGraphMachine(sm).get_graph().write_png("microwave.png")

    assert sm.current_state.id == "unplugged"
    sm.send("plug-in")

    assert "idle" in sm.current_state_value
    assert "plugged-in" in sm.current_state_value

    sm.send("start")

    assert "cooking" in sm.current_state_value
    assert "idle" not in sm.current_state_value
    assert "plugged-in" in sm.current_state_value

    sm.send("unplug")

    assert "unplugged" in sm.current_state_value
    assert "idle" not in sm.current_state_value
    assert "plugged-in" not in sm.current_state_value
    assert "cooking" not in sm.current_state_value


class TestMicrowave:
    @pytest.fixture()
    def microwave_cls(self):
        class MicroWave(StateChart):
            door_closed: bool = True

            class oven(State.Compound, name="Microwave oven", parallel=True):
                class engine(State.Compound):
                    off = State(initial=True)

                    class on(State.Compound):
                        idle = State(initial=True)
                        cooking = State()

                        idle.to(cooking, cond="In('closed')")
                        cooking.to(idle, cond="In('open')")
                        time = cooking.to.itself(internal=True, on="increment_timer")

                        def increment_timer(self):
                            self.timer += 1

                    assert isinstance(on, State)  # so mypy stop complaining
                    on.to(off, event="turn-off")
                    off.to(on, event="turn-on")
                    on.to(off, cond="timer >= cook_time")  # eventless transition

                class door(State.Compound):
                    closed = State(initial=True)
                    open = State()

                    closed.to(open, event="door.open")
                    open.to(closed, event="door.close")

                    def on_enter_open(self):
                        self.door_closed = False

                    def on_enter_closed(self):
                        self.door_closed = True

            def __init__(self):
                self.cook_time = 5
                self.timer = 0
                super().__init__()

        return MicroWave

    def test_microwave(self, microwave_cls):
        sm = microwave_cls()

        assert {"door", "closed", "oven", "engine", "off"} == {*sm.current_state_value}
        assert sm.door_closed is True

        sm.send("turn-on")
        assert {"door", "closed", "oven", "engine", "on", "cooking"} == {*sm.current_state_value}

        sm.send("door.open")
        assert {"door", "open", "oven", "engine", "on", "idle"} == {*sm.current_state_value}
        assert sm.door_closed is False

        sm.send("door.close")
        assert {"door", "closed", "oven", "engine", "on", "cooking"} == {*sm.current_state_value}
        assert sm.door_closed is True

        for _ in range(5):
            sm.send("time")

        assert {"door", "closed", "oven", "engine", "off"} == {*sm.current_state_value}
        assert sm.door_closed is True
