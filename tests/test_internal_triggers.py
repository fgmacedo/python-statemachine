"""Which queue a trigger asked to be internal goes to, and what its caller gets back.

The internal queue holds what the machine raises while it runs a step, so it is processed
within that macrostep, before any pending external event. A trigger put from outside a step
has no macrostep to join: it goes to the external queue, where its caller gets its result,
its exception or ``TransitionNotAllowed``. A delay can never be internal, since a step takes
no time; asking for both is an invalid definition.

Theme: the beacons of Gondor, lit from inside the chain or called for from afar.
"""

from inspect import isawaitable

import pytest
from statemachine.engines.base import _in_processing_loop
from statemachine.exceptions import InvalidDefinition
from statemachine.exceptions import TransitionNotAllowed
from statemachine.io.scxml.processor import SCXMLProcessor

from statemachine import Event
from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine

DELAYED_INTERNAL = "cannot be both delayed and internal"


class Beacons(StateChart):
    dark = State(initial=True)
    lit = State(final=True)

    light = Event(dark.to(lit, on="kindle"), internal=True)

    def kindle(self):
        return "kindled"


async def settle(result):
    return await result if isawaitable(result) else result


class TestFromACallback:
    async def test_a_declared_internal_event_runs_before_a_pending_external_event(self, sm_runner):
        class Muster(StateChart):
            camp = State(initial=True)
            riding = State(final=True)
            besieged = State(final=True)

            summon = camp.to.itself(internal=True, on="call")
            ride = Event(camp.to(riding), internal=True)
            siege = camp.to(besieged)

            def call(self):
                self.siege.put()
                self.ride.put()

        sm = await sm_runner.start(Muster)

        await sm_runner.send(sm, "summon")

        assert sm.configuration_values == {"riding"}

    async def test_an_internal_event_raised_while_entering_the_initial_state_runs_first(
        self, sm_runner
    ):
        class Watch(StateChart):
            dark = State(initial=True)
            lit = State(final=True)
            fallen = State(final=True)

            light = Event(dark.to(lit), internal=True)
            fall = dark.to(fallen)

            def on_enter_dark(self):
                self.fall.put()
                self.light.put()

        sm = await sm_runner.start(Watch)

        assert sm.configuration_values == {"lit"}


class TestFromOutside:
    @pytest.mark.parametrize(
        "trigger",
        [
            pytest.param(lambda sm: sm.light(), id="method"),
            pytest.param(lambda sm: sm.send("light"), id="send"),
            pytest.param(lambda sm: sm.raise_("light"), id="raise"),
        ],
    )
    async def test_a_declared_internal_event_returns_the_callback_result(self, sm_runner, trigger):
        sm = await sm_runner.start(Beacons)

        assert await settle(trigger(sm)) == "kindled"
        assert sm.configuration_values == {"lit"}

    async def test_an_internal_event_with_no_transition_raises_on_a_state_machine(self, sm_runner):
        class StrictBeacons(StateMachine):
            dark = State(initial=True)
            lit = State()

            light = dark.to(lit)
            douse = Event(lit.to(dark), internal=True)

        sm = await sm_runner.start(StrictBeacons)

        with pytest.raises(TransitionNotAllowed):
            await sm_runner.send(sm, "douse")

    async def test_an_exception_from_a_declared_internal_event_reaches_the_caller(self, sm_runner):
        class FailingBeacons(StateChart):
            catch_errors_as_events = False

            dark = State(initial=True)
            lit = State(final=True)

            light = Event(dark.to(lit, on="kindle"), internal=True)

            def kindle(self):
                raise RuntimeError("the fire would not catch")

        sm = await sm_runner.start(FailingBeacons)

        with pytest.raises(RuntimeError, match="the fire would not catch"):
            await sm_runner.send(sm, "light")

    async def test_a_fresh_async_machine_runs_a_declared_internal_event_on_its_first_await(
        self,
    ):
        class AsyncBeacons(Beacons):
            async def kindle(self):
                return "kindled"

        sm = AsyncBeacons()

        assert await sm.light() == "kindled"
        assert sm.configuration_values == {"lit"}

    @pytest.mark.parametrize("outcome", ["completes", "raises"])
    async def test_the_processing_loop_leaves_the_context_as_it_found_it(self, sm_runner, outcome):
        class Signal(StateChart):
            catch_errors_as_events = False

            dark = State(initial=True)
            lit = State(final=True)

            light = Event(dark.to(lit, on="kindle"), internal=True)
            fail = dark.to.itself(internal=True, on="stumble")

            def kindle(self):
                return "kindled"

            def stumble(self):
                raise RuntimeError("stumbled")

        sm = await sm_runner.start(Signal)
        if outcome == "raises":
            with pytest.raises(RuntimeError, match="stumbled"):
                await sm_runner.send(sm, "fail")

        assert _in_processing_loop.get() is False
        assert await settle(sm.raise_("light")) == "kindled"


class TestDelayedInternal:
    def test_a_declaration_cannot_be_both_delayed_and_internal(self):
        with pytest.raises(InvalidDefinition, match=DELAYED_INTERNAL):

            class DelayedBeacons(StateChart):
                dark = State(initial=True)
                lit = State(final=True)

                light = Event(dark.to(lit), delay=50, internal=True)

    def test_a_compound_declaration_cannot_be_both_delayed_and_internal(self):
        with pytest.raises(InvalidDefinition, match=DELAYED_INTERNAL):

            class DelayedBeacons(StateChart):
                class chain(State.Compound):
                    dark = State(initial=True)
                    lit = State(final=True)

                    light = Event(dark.to(lit), delay=50, internal=True)

    @pytest.mark.parametrize(
        "trigger",
        [
            pytest.param(lambda sm: sm.raise_("light", delay=50), id="raise"),
            pytest.param(lambda sm: sm.send("light", delay=50, internal=True), id="send"),
            pytest.param(lambda sm: sm.send("light", delay=50), id="declared-internal"),
        ],
    )
    async def test_a_trigger_cannot_be_both_delayed_and_internal(self, sm_runner, trigger):
        sm = await sm_runner.start(Beacons)

        with pytest.raises(InvalidDefinition, match=DELAYED_INTERNAL):
            await settle(trigger(sm))

        assert sm.configuration_values == {"dark"}

    def test_an_scxml_send_to_internal_cannot_have_a_delay(self):
        scxml = """
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="dark">
          <state id="dark">
            <onentry>
              <send event="light" target="#_internal" delay="50ms"/>
            </onentry>
            <transition event="light" target="lit"/>
          </state>
          <final id="lit"/>
        </scxml>
        """
        processor = SCXMLProcessor()
        processor.parse_scxml("delayed_internal", scxml)

        with pytest.raises(InvalidDefinition, match=DELAYED_INTERNAL):
            processor.start()
