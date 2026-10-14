"""``type="internal"`` keeps the SCXML meaning: it only applies to a compound source.

On an atomic source the transition is external, so targeting itself runs ``onexit`` and
``onentry`` again.

Theme: a lantern that is relit.
"""

import pytest
from statemachine.io.scxml.processor import SCXMLProcessor

pytestmark = pytest.mark.scxml

LANTERN_SCXML = """
<scxml initial="lit" datamodel="python">
  <datamodel>
    <data id="lightings" expr="0"/>
    <data id="snuffs" expr="0"/>
  </datamodel>
  <state id="lit">
    <onentry><assign location="lightings" expr="lightings + 1"/></onentry>
    <onexit><assign location="snuffs" expr="snuffs + 1"/></onexit>
    <transition event="relight" target="lit" type="internal"/>
  </state>
</scxml>
"""


def test_internal_self_transition_on_an_atomic_state_is_external():
    processor = SCXMLProcessor()
    processor.parse_scxml("lantern", LANTERN_SCXML)
    sm = processor.start()

    sm.send("relight")

    assert (sm.model.lightings, sm.model.snuffs) == (2, 1)
