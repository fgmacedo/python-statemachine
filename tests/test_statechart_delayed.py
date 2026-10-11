"""Delayed event sends and cancellations.

Tests exercise queuing events with a delay (fires after elapsed time),
cancelling delayed events before they fire, zero-delay immediate firing,
and the Event(delay=...) definition syntax.

Theme: Beacons of Gondor — signal fires propagate with timing.
"""

import asyncio
import time

import pytest
from statemachine.engines import async_
from statemachine.engines import sync
from statemachine.event import BoundEvent

from statemachine import Event
from statemachine import State
from statemachine import StateChart
from statemachine import event_data


@pytest.mark.timeout(10)
class TestDelayedEvents:
    async def test_delayed_event_fires_after_delay(self, sm_runner):
        """Queuing a delayed event does not fire immediately; processing after delay does."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            first_lit = State()
            all_lit = State(final=True)

            light_first = dark.to(first_lit)
            light_all = first_lit.to(all_lit)

        sm = await sm_runner.start(BeaconsOfGondor)
        await sm_runner.send(sm, "light_first")
        assert "first_lit" in sm.configuration_values

        # Queue the event with delay without triggering the processing loop
        event = BoundEvent(id="light_all", name="Light all", delay=50, _sm=sm)
        event.put()

        # Not yet processed
        assert "first_lit" in sm.configuration_values

        await asyncio.sleep(0.1)
        await sm_runner.processing_loop(sm)
        assert "all_lit" in sm.configuration_values

    async def test_cancel_delayed_event(self, sm_runner):
        """Cancelled delayed events do not fire."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = await sm_runner.start(BeaconsOfGondor)
        # Queue delayed event
        event = BoundEvent(id="light", name="Light", delay=500, _sm=sm)
        event.put(send_id="beacon_signal")

        sm.cancel_event("beacon_signal")

        await asyncio.sleep(0.1)
        await sm_runner.processing_loop(sm)
        assert "dark" in sm.configuration_values

    async def test_zero_delay_fires_immediately(self, sm_runner):
        """delay=0 fires immediately."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = await sm_runner.start(BeaconsOfGondor)
        await sm_runner.send(sm, "light", delay=0)
        assert "lit" in sm.configuration_values

    async def test_delayed_event_on_event_definition(self, sm_runner):
        """Event(transitions, delay=100) syntax queues with a delay."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = Event(dark.to(lit), delay=50)

        sm = await sm_runner.start(BeaconsOfGondor)
        # Queue via BoundEvent.put() to avoid blocking in processing_loop
        sm.light.put()

        # Not yet processed
        assert "dark" in sm.configuration_values

        await asyncio.sleep(0.1)
        await sm_runner.processing_loop(sm)
        assert "lit" in sm.configuration_values

    async def test_delay_is_measured_on_the_monotonic_clock(self, sm_runner, clock):
        """A delay comes due by ``time.monotonic``, which a wall-clock step cannot move.

        The trigger is stamped and checked on the same monotonic clock: here a fake one that
        moves only when the test moves it. A stamp on one clock checked against another would
        hold the beacon unlit.
        """

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = await sm_runner.start(BeaconsOfGondor)
        BoundEvent(id="light", name="Light", delay=50, _sm=sm).put()
        clock.now += 0.05

        await sm_runner.processing_loop(sm)

        assert "lit" in sm.configuration_values

    def test_triggers_are_stamped_and_checked_on_the_monotonic_clock(self):
        clocks = (event_data.monotonic, sync.monotonic, async_.monotonic)

        assert clocks == (time.monotonic, time.monotonic, time.monotonic)

    @pytest.mark.parametrize(
        ("delay", "due"),
        [
            pytest.param(None, 1000.0, id="none"),
            pytest.param(0, 1000.0, id="zero"),
            pytest.param(1, 1000.001, id="one-millisecond"),
            pytest.param(50, 1000.05, id="fifty-milliseconds"),
            pytest.param(-50, 999.95, id="negative-already-due"),
        ],
    )
    def test_a_delay_in_milliseconds_comes_due_that_many_thousandths_later(
        self, clock, delay, due
    ):
        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = BeaconsOfGondor()

        trigger = BoundEvent(id="light", name="Light", delay=delay, _sm=sm).put()

        assert trigger.execution_time == pytest.approx(due, abs=1e-9)

    async def test_a_delayed_event_queued_from_a_callback_fires_when_due(self, sm_runner, clock):
        """The callback runs inside the processing loop, which then waits on the event it queued.

        Every reading of the clock is 10 ms later than the last, so the beacon comes due after
        a few turns of the loop however long each takes.
        """

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            first_lit = State()
            all_lit = State(final=True)

            light_first = dark.to(first_lit, after="spread")
            light_all = first_lit.to(all_lit)

            def spread(self):
                BoundEvent(id="light_all", name="Light all", delay=50, _sm=self).put()

        clock.step = 0.01
        sm = await sm_runner.start(BeaconsOfGondor)

        await sm_runner.send(sm, "light_first")

        assert sm.configuration_values == {"all_lit"}

    @pytest.mark.parametrize(
        "started",
        [pytest.param(False, id="before-it-runs"), pytest.param(True, id="while-it-awaits")],
    )
    async def test_a_caller_that_stops_waiting_does_not_stop_its_delayed_event(
        self, clock, started
    ):
        class Beacon(StateChart):
            dark = State(initial=True)

            signal = dark.to.itself(internal=True, on="flare")

            def __init__(self, *args, **kwargs):
                self.flares = []
                super().__init__(*args, **kwargs)

            async def flare(self, which):
                self.flares.append(which)

        sm = Beacon()
        await sm.activate_initial_state()
        holding = asyncio.create_task(sm.send("signal", delay=20, which="second"))
        await asyncio.sleep(0)
        waiting = asyncio.create_task(sm.send("signal", delay=10, which="first"))
        if started:
            await asyncio.sleep(0)

        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        clock.now += 1.0
        await holding

        assert sm.flares == ["first", "second"]
