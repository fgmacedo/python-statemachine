from statemachine import State
from statemachine import StateMachine
from statemachine.event import Event


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


class TestExplicitEvent:
    def test_accept_event_instance(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            start = Event(created.to(started))

        assert [e.id for e in StartMachine.events] == ["start"]
        assert [e.name for e in StartMachine.events] == ["Start"]
        assert StartMachine.start.name == "Start"

        sm = StartMachine()
        sm.send("start")
        assert sm.current_state == sm.started

    def test_accept_event_name(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            start = Event(created.to(started), name="Launch the machine")

        assert [e.id for e in StartMachine.events] == ["start"]
        assert [e.name for e in StartMachine.events] == ["Launch the machine"]
        assert StartMachine.start.name == "Launch the machine"

    def test_derive_name_from_id(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            launch_the_machine = Event(created.to(started))

        assert [e.id for e in StartMachine.events] == ["launch_the_machine"]
        assert [e.name for e in StartMachine.events] == ["Launch the machine"]
        assert StartMachine.launch_the_machine.name == "Launch the machine"
