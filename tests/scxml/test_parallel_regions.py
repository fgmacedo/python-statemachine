"""A transition that targets a parallel state and a state inside one of its regions.

The region holding the targeted state enters that state and not its initial one; every other
region enters its initial state.

Theme: the beacons, one of them already lit.
"""

import pytest
from statemachine.io.scxml.processor import SCXMLProcessor

pytestmark = pytest.mark.scxml

BEACONS_SCXML = """
<scxml initial="dark">
  <state id="dark">
    <transition event="light" target="east_lit beacons"/>
  </state>
  <parallel id="beacons">
    <state id="east" initial="east_dark">
      <state id="east_dark"/>
      <state id="east_lit"/>
    </state>
    <state id="west" initial="west_dark">
      <state id="west_dark"/>
    </state>
  </parallel>
</scxml>
"""


def test_a_region_with_a_targeted_state_does_not_also_enter_its_initial_state():
    processor = SCXMLProcessor()
    processor.parse_scxml("beacons", BEACONS_SCXML)
    sm = processor.start()

    sm.send("light")

    assert set(sm.configuration_values) == {"beacons", "east", "east_lit", "west", "west_dark"}
