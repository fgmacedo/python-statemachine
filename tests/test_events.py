from statemachine import State
from statemachine import StateMachine


def test_assign_events_on_transitions():
    class TrafficLightMachine(StateMachine):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        green.to(yellow, event="cycle slowdown slowdown")
        yellow.to(red, event="cycle stop")
        red.to(green, event="cycle go")

        def on_cycle(self, event_data, event: str):
            assert event_data.event == event
            return (
                f"Running {event} from {event_data.transition.source.id} to "
                f"{event_data.transition.target.id}"
            )

    sm = TrafficLightMachine()

    assert sm.send("cycle") == "Running cycle from green to yellow"
    assert sm.send("cycle") == "Running cycle from yellow to red"
    assert sm.send("cycle") == "Running cycle from red to green"
