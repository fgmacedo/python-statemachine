"""End-to-end behavior of native statecharts on both sync and async engines."""

from statemachine.io import load

MICROWAVE = """
name: Microwave
datamodel:
  - {id: door_closed, expr: "True"}
  - {id: power, expr: "0"}
  - {id: remaining, expr: "2"}
states:
  off:
    initial: true
    transitions:
      - event: turn_on
        target: cooking
        cond: "door_closed"
  cooking:
    enter:
      - assign: {location: power, expr: "100"}
    transitions:
      - event: tick
        target: cooking
        cond: "remaining > 0"
        on:
          - assign: {location: remaining, expr: "remaining - 1"}
      - target: off          # eventless: fires when remaining <= 0
        cond: "remaining <= 0"
"""


class TestNativeBehavior:
    async def test_microwave_runs(self, sm_runner):
        sm = await sm_runner.start(load(MICROWAVE, format="yaml"))
        assert "off" in sm.configuration_values

        await sm_runner.send(sm, "turn_on")
        assert "cooking" in sm.configuration_values
        assert sm.model.power == 100

        await sm_runner.send(sm, "tick")
        assert sm.model.remaining == 1
        assert "cooking" in sm.configuration_values

        await sm_runner.send(sm, "tick")
        # remaining hits 0, the eventless transition returns to off
        assert "off" in sm.configuration_values

    async def test_safe_expression_guards(self, sm_runner):
        doc = """
        datamodel:
          - {id: x, expr: "7"}
        states:
          a:
            initial: true
            transitions:
              - {event: go, target: high, cond: "x > 5 and x < 10"}
              - {event: go, target: low}
          high: {final: true}
          low: {final: true}
        """
        sm = await sm_runner.start(load(doc, format="yaml"))
        await sm_runner.send(sm, "go")
        assert "high" in sm.configuration_values
