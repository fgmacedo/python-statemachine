from statemachine import StateMachine, State


class TrafficLightMachine(StateMachine):  # type: ignore
    "A traffic light machine"
    green = State("Green", initial=True)
    yellow = State("Yellow")
    red = State("Red")

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def on_cycle(self, event_data=None):
        return "Running {} from {} to {}".format(
            event_data.event.name,
            event_data.transition.source.identifier,
            event_data.transition.destination.identifier,
        )
