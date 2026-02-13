"""Delayed event sends and cancellations.

Tests exercise queuing events with a delay (fires after elapsed time),
cancelling delayed events before they fire, zero-delay immediate firing,
and the Event(delay=...) definition syntax.

Theme: Beacons of Gondor — signal fires propagate with timing.
"""

import time

import pytest
from statemachine.event import BoundEvent

from statemachine import Event
from statemachine import State
from statemachine import StateChart


@pytest.mark.timeout(10)
class TestDelayedEvents:
    def test_delayed_event_fires_after_delay(self):
        """Queuing a delayed event does not fire immediately; processing after delay does."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            first_lit = State()
            all_lit = State(final=True)

            light_first = dark.to(first_lit)
            light_all = first_lit.to(all_lit)

        sm = BeaconsOfGondor()
        sm.send("light_first")
        assert "first_lit" in sm.configuration_values

        # Queue the event with delay without triggering the processing loop
        event = BoundEvent(id="light_all", name="Light all", delay=50, _sm=sm)
        event.put()

        # Not yet processed
        assert "first_lit" in sm.configuration_values

        time.sleep(0.1)
        sm._processing_loop()
        assert "all_lit" in sm.configuration_values

    def test_cancel_delayed_event(self):
        """Cancelled delayed events do not fire."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = BeaconsOfGondor()
        # Queue delayed event
        event = BoundEvent(id="light", name="Light", delay=500, _sm=sm)
        event.put(send_id="beacon_signal")

        sm.cancel_event("beacon_signal")

        time.sleep(0.1)
        sm._processing_loop()
        assert "dark" in sm.configuration_values

    def test_zero_delay_fires_immediately(self):
        """delay=0 fires immediately."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = dark.to(lit)

        sm = BeaconsOfGondor()
        sm.send("light", delay=0)
        assert "lit" in sm.configuration_values

    def test_delayed_event_on_event_definition(self):
        """Event(transitions, delay=100) syntax queues with a delay."""

        class BeaconsOfGondor(StateChart):
            dark = State(initial=True)
            lit = State(final=True)

            light = Event(dark.to(lit), delay=50)

        sm = BeaconsOfGondor()
        # Queue via BoundEvent.put() to avoid blocking in processing_loop
        event = BoundEvent(id="light", name="Light", delay=50, _sm=sm)
        event.put()

        # Not yet processed
        assert "dark" in sm.configuration_values

        time.sleep(0.1)
        sm._processing_loop()
        assert "lit" in sm.configuration_values
