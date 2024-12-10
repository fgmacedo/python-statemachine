import pytest

from statemachine.io.scxml.processor import SCXMLProcessor

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
def test_microwave():
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
    # assert "plugged-in" in sm.current_state_value

    sm.send("unplug")

    assert "unplugged" in sm.current_state_value
    assert "idle" not in sm.current_state_value
    assert "plugged-in" not in sm.current_state_value
    assert "cooking" not in sm.current_state_value
