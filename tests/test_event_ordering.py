"""Events due at the same moment are processed in the order they were sent.

Both queues are priority queues ordered by each trigger's due time. Triggers
stamped with the same time, as a coarse clock stamps events sent close together,
must still come out in the order they went in.

Theme: the Riders of Rohan answering the muster, each in turn.
"""

import pytest
from statemachine.event import BoundEvent

from statemachine import State
from statemachine import StateChart


class Muster(StateChart):
    camp = State(initial=True)

    call = camp.to.itself(internal=True, on="call_riders")
    ride = camp.to.itself(internal=True, on="answer")

    def __init__(self, *args, **kwargs):
        self.answered = []
        super().__init__(*args, **kwargs)

    def call_riders(self, riders):
        for rider in range(riders):
            BoundEvent(id="ride", name="Ride", internal=True, _sm=self).put(rider=rider)

    def answer(self, rider):
        self.answered.append(rider)


@pytest.fixture(autouse=True)
def stamped_alike(clock):
    """Stamp every trigger in these tests with the same time: the clock never moves."""
    return clock


@pytest.mark.timeout(10)
@pytest.mark.parametrize("riders", [0, 1, 2, 20])
class TestEventsDueTogether:
    async def test_internal_events_run_in_the_order_raised(self, sm_runner, riders):
        sm = await sm_runner.start(Muster)

        await sm_runner.send(sm, "call", riders=riders)

        assert sm.answered == list(range(riders))

    async def test_external_events_run_in_the_order_sent(self, sm_runner, riders):
        sm = await sm_runner.start(Muster)
        for rider in range(riders):
            BoundEvent(id="ride", name="Ride", _sm=sm).put(rider=rider)

        await sm_runner.processing_loop(sm)

        assert sm.answered == list(range(riders))
