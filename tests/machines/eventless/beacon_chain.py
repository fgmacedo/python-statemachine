from statemachine import State
from statemachine import StateChart


class BeaconChain(StateChart):
    class beacons(State.Compound):
        first = State(initial=True)
        last = State(final=True)

        first.to(last)

    signal_received = State(final=True)
    done_state_beacons = beacons.to(signal_received)
