from statemachine import State
from statemachine import StateMachine


def test_assign_events_on_transitions():
    class TrafficLightMachine(StateMachine):
        "A traffic light machine"
        green = State("Green", initial=True)
        yellow = State("Yellow")
        red = State("Red")

        green.to(yellow, event="cycle slowdown slowdown")
        yellow.to(red, event="cycle stop")
        red.to(green, event="cycle go")

        def on_cycle(self, event_data=None):
            return "Running {} from {} to {}".format(
                event_data.event,
                event_data.transition.source.id,
                event_data.transition.target.id,
            )

    sm = TrafficLightMachine()

    assert sm.send("cycle") == "Running cycle from green to yellow"
    assert sm.send("cycle") == "Running cycle from yellow to red"
    assert sm.send("cycle") == "Running cycle from red to green"
