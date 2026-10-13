"""Which queue a trigger asked to be internal goes to, and what its caller gets back.

The internal queue holds what the machine raises while it runs a step, so it is processed
within that macrostep, before any pending external event. A trigger put from outside a step
has no macrostep to join: it goes to the external queue, where its caller gets its result,
its exception or ``TransitionNotAllowed``. A delay can never be internal, since a step takes
no time; asking for both is an invalid definition.

Theme: the beacons of Gondor, lit from inside the chain or called for from afar.
"""

import asyncio
import json
import threading
from inspect import isawaitable

import pytest
from statemachine.engines.base import _running_engine
from statemachine.exceptions import InvalidDefinition
from statemachine.exceptions import TransitionNotAllowed
from statemachine.io.loader import load
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

    def test_send_with_internal_false_overrides_the_declaration(self):
        class Muster(StateChart):
            camp = State(initial=True)
            riding = State(final=True)
            besieged = State(final=True)

            summon = camp.to.itself(internal=True, on="call")
            ride = Event(camp.to(riding), internal=True)
            siege = camp.to(besieged)

            def call(self):
                self.send("siege")
                self.send("ride", internal=False)

        sm = Muster()

        sm.send("summon")

        assert sm.configuration_values == {"besieged"}


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

        assert _running_engine.get() is None
        assert await settle(sm.raise_("light")) == "kindled"


class TestWhoIsRunningTheStep:
    """The internal queue belongs to the step of one machine, in one thread or task."""

    @pytest.mark.timeout(10)
    async def test_a_coroutine_outside_the_loop_gets_its_result_while_another_holds_it(self):
        paused = asyncio.Event()
        resume = asyncio.Event()

        class Relay(StateChart):
            dark = State(initial=True)
            waiting = State()
            lit = State(final=True)

            hold = dark.to(waiting, on="pause")
            light = Event(waiting.to(lit, on="kindle"), internal=True)

            async def pause(self):
                paused.set()
                await resume.wait()
                return "held"

            def kindle(self):
                return "kindled"

        async def light():
            return await sm.light()

        sm = Relay()
        await sm.activate_initial_state()
        holding = asyncio.create_task(sm.send("hold"))
        await paused.wait()
        lighting = asyncio.create_task(light())
        await asyncio.sleep(0)
        resume.set()

        assert await asyncio.gather(holding, lighting) == ["held", "kindled"]

    @pytest.mark.timeout(10)
    def test_a_thread_raising_while_another_runs_the_loop_queues_behind_its_sends(self):
        in_step = threading.Event()
        release = threading.Event()

        class Watch(StateChart):
            dark = State(initial=True)
            waiting = State()
            lit = State(final=True)
            besieged = State(final=True)

            hold = dark.to(waiting, on="pause")
            light = waiting.to(lit)
            siege = waiting.to(besieged)

            def pause(self):
                in_step.set()
                release.wait(timeout=5)

        sm = Watch()
        holder = threading.Thread(target=sm.send, args=("hold",))
        holder.start()
        assert in_step.wait(timeout=5)

        sm.send("siege")
        sm.raise_("light")
        release.set()
        holder.join(timeout=5)

        assert sm.configuration_values == {"besieged"}

    async def test_a_callback_raising_on_another_machine_gets_its_result(self, sm_runner):
        other = await sm_runner.start(Beacons)

        class Lighter(StateChart):
            idle = State(initial=True)
            done = State(final=True)

            reach = idle.to(done, on="light_other")

            def light_other(self):
                return other.raise_("light")

        sm = await sm_runner.start(Lighter)

        assert await settle(await sm_runner.send(sm, "reach")) == "kindled"
        assert other.configuration_values == {"lit"}

    async def test_a_callback_triggering_a_disallowed_event_on_another_machine_raises(
        self, sm_runner
    ):
        class StrictBeacons(StateMachine):
            dark = State(initial=True)
            lit = State()

            light = dark.to(lit)
            douse = Event(lit.to(dark), internal=True)

        other = await sm_runner.start(StrictBeacons)

        class Douser(StateChart):
            catch_errors_as_events = False

            idle = State(initial=True)
            done = State(final=True)

            reach = idle.to(done, on="douse_other")

            def douse_other(self):
                return other.douse()

        sm = await sm_runner.start(Douser)

        with pytest.raises(TransitionNotAllowed):
            await settle(await sm_runner.send(sm, "reach"))


class TestDelayedInternal:
    @pytest.mark.parametrize(
        ("attribute", "kwargs", "event_id"),
        [
            pytest.param("light", {}, "light", id="attribute"),
            pytest.param("light", {"id": "kindle"}, "kindle", id="explicit-id"),
            pytest.param("error_light", {}, "error_light", id="prefixed"),
        ],
    )
    def test_a_declaration_cannot_be_both_delayed_and_internal(self, attribute, kwargs, event_id):
        with pytest.raises(InvalidDefinition, match=f"^Event '{event_id}' {DELAYED_INTERNAL}"):
            type(
                "DelayedBeacons",
                (StateChart,),
                {
                    "dark": (dark := State(initial=True)),
                    "lit": (lit := State(final=True)),
                    attribute: Event(dark.to(lit), delay=50, internal=True, **kwargs),
                },
            )

    @pytest.mark.parametrize(
        ("attribute", "kwargs", "event_id"),
        [
            pytest.param("light", {}, "light", id="attribute"),
            pytest.param("light", {"id": "kindle"}, "kindle", id="explicit-id"),
            pytest.param("error_light", {}, "error_light", id="prefixed"),
        ],
    )
    def test_a_compound_declaration_cannot_be_both_delayed_and_internal(
        self, attribute, kwargs, event_id
    ):
        with pytest.raises(InvalidDefinition, match=f"^Event '{event_id}' {DELAYED_INTERNAL}"):
            type(
                "chain",
                (State.Compound,),
                {
                    "dark": (dark := State(initial=True)),
                    "lit": (lit := State(final=True)),
                    attribute: Event(dark.to(lit), delay=50, internal=True, **kwargs),
                },
            )

    def test_a_declaration_without_transitions_cannot_be_both_delayed_and_internal(self):
        with pytest.raises(InvalidDefinition, match=f"^Event 'light' {DELAYED_INTERNAL}"):

            class DelayedBeacons(StateChart):
                dark = State(initial=True)
                lit = State(final=True)

                kindle = dark.to(lit)
                light = Event(delay=50, internal=True)

    def test_a_compound_declaration_without_transitions_cannot_be_both_delayed_and_internal(
        self,
    ):
        with pytest.raises(InvalidDefinition, match=f"^Event 'light' {DELAYED_INTERNAL}"):

            class DelayedBeacons(StateChart):
                class chain(State.Compound):
                    dark = State(initial=True)
                    lit = State(final=True)

                    kindle = dark.to(lit)
                    light = Event(delay=50, internal=True)

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

    @pytest.mark.timeout(10)
    async def test_a_declared_internal_event_can_be_sent_later_as_external(self, sm_runner):
        sm = await sm_runner.start(Beacons)

        assert await sm_runner.send(sm, "light", delay=10, internal=False) == "kindled"

    @pytest.mark.parametrize("delay", ['delay="50ms"', "delayexpr=\"'50ms'\""])
    @pytest.mark.parametrize("target", ["#_internal", "internal"])
    def test_an_scxml_send_to_internal_with_a_delay_fails_to_load(self, target, delay):
        scxml = f"""
        <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="dark">
          <state id="dark">
            <onentry>
              <send event="light" target="{target}" {delay}/>
            </onentry>
            <transition event="light" target="lit"/>
          </state>
          <final id="lit"/>
        </scxml>
        """

        with pytest.raises(InvalidDefinition, match=DELAYED_INTERNAL):
            SCXMLProcessor().parse_scxml("delayed_internal", scxml)

    @pytest.mark.parametrize("validate", [True, False])
    def test_a_native_send_to_internal_with_a_delay_fails_to_load(self, validate):
        document = {
            "name": "DelayedInternal",
            "states": {
                "dark": {
                    "initial": True,
                    "enter": [
                        {"send": {"event": "light", "target": "#_internal", "delay": "50ms"}}
                    ],
                    "transitions": [{"event": "light", "target": "lit"}],
                },
                "lit": {"final": True},
            },
        }

        with pytest.raises(InvalidDefinition):
            load(json.dumps(document), format="json", validate=validate)


class DelayedBeacons(StateChart):
    dark = State(initial=True)
    lit = State(final=True)

    signal = Event(dark.to(lit, on="kindle"), delay=60_000)

    def kindle(self):
        return "kindled"


class TestExplicitZeroDelay:
    @pytest.mark.timeout(10)
    async def test_send_with_delay_zero_overrides_the_declared_delay(self, sm_runner):
        sm = await sm_runner.start(DelayedBeacons)

        assert await sm_runner.send(sm, "signal", delay=0) == "kindled"
        assert sm.configuration_values == {"lit"}

    @pytest.mark.timeout(10)
    async def test_raise_with_delay_zero_overrides_the_declared_delay(self, sm_runner):
        sm = await sm_runner.start(DelayedBeacons)

        assert await settle(sm.raise_("signal", delay=0)) == "kindled"
        assert sm.configuration_values == {"lit"}

    async def test_raise_without_delay_keeps_the_declared_delay(self, sm_runner):
        sm = await sm_runner.start(DelayedBeacons)

        with pytest.raises(InvalidDefinition, match=f"^Event 'signal' {DELAYED_INTERNAL}"):
            await settle(sm.raise_("signal"))

        assert sm.configuration_values == {"dark"}
