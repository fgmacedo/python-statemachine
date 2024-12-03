import pytest

from statemachine import State
from statemachine import StateMachine
from statemachine.event import Event
from statemachine.exceptions import InvalidDefinition


def test_assign_events_on_transitions():
    class TrafficLightMachine(StateMachine):
        "A traffic light machine"

        green = State(initial=True)
        yellow = State()
        red = State()

        green.to(yellow, event="cycle slowdown")
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

            start = Event(created.to(started), name="Start the machine")

        assert [e.id for e in StartMachine.events] == ["start"]
        assert [e.name for e in StartMachine.events] == ["Start the machine"]
        assert StartMachine.start.name == "Start the machine"

    def test_derive_name_from_id(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            launch_the_machine = Event(created.to(started))

        assert list(StartMachine.events) == ["launch_the_machine"]
        assert [e.id for e in StartMachine.events] == ["launch_the_machine"]
        assert [e.name for e in StartMachine.events] == ["Launch the machine"]
        assert StartMachine.launch_the_machine.name == "Launch the machine"
        assert str(StartMachine.launch_the_machine) == "launch_the_machine"
        assert StartMachine.launch_the_machine == StartMachine.launch_the_machine.id

    def test_not_derive_name_from_id_if_not_event_class(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State(final=True)

            launch_the_machine = created.to(started)

        assert list(StartMachine.events) == ["launch_the_machine"]
        assert [e.id for e in StartMachine.events] == ["launch_the_machine"]
        assert [e.name for e in StartMachine.events] == ["launch_the_machine"]
        assert StartMachine.launch_the_machine.name == "launch_the_machine"
        assert str(StartMachine.launch_the_machine) == "launch_the_machine"
        assert StartMachine.launch_the_machine == StartMachine.launch_the_machine.id

    def test_raise_invalid_definition_if_event_name_cannot_be_derived(self):
        with pytest.raises(InvalidDefinition, match="has no id"):

            class StartMachine(StateMachine):
                created = State(initial=True)
                started = State()

                launch = Event(created.to(started))

                started.to.itself(event=Event())  # event id not defined

    def test_derive_from_id(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State()

            created.to(started, event=Event("launch_rocket"))

        assert StartMachine.launch_rocket.name == "Launch rocket"

    def test_of_passing_event_as_parameters(self):
        class TrafficLightMachine(StateMachine):
            "A traffic light machine"

            green = State(initial=True)
            yellow = State()
            red = State()

            cycle = Event(name="Loop")
            slowdown = Event(name="slow down")
            stop = Event(name="Please stop")
            go = Event(name="Go! Go! Go!")

            green.to(yellow, event=[cycle, slowdown])
            yellow.to(red, event=[cycle, stop])
            red.to(green, event=[cycle, go])

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
        assert sm.cycle.name == "Loop"
        assert sm.slowdown.name == "slow down"
        assert sm.stop.name == "Please stop"
        assert sm.go.name == "Go! Go! Go!"

    def test_mixing_event_and_parameters(self):
        class TrafficLightMachine(StateMachine):
            "A traffic light machine"

            green = State(initial=True)
            yellow = State()
            red = State()

            cycle = Event(
                green.to(yellow, event=Event("slowdown", name="Slow down"))
                | yellow.to(red, event=Event("stop", name="Please stop!"))
                | red.to(green, event=Event("go", name="Go! Go! Go!")),
                name="Loop",
            )

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
        assert sm.cycle.name == "Loop"
        assert sm.slowdown.name == "Slow down"
        assert sm.stop.name == "Please stop!"
        assert sm.go.name == "Go! Go! Go!"

    def test_name_derived_from_identifier(self):
        class TrafficLightMachine(StateMachine):
            "A traffic light machine"

            green = State(initial=True)
            yellow = State()
            red = State()

            cycle = Event(name="Loop")
            slow_down = Event()
            green.to(yellow, event=[cycle, slow_down])
            yellow.to(red, event=[cycle, "stop"])
            red.to(green, event=[cycle, "go"])

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
        assert sm.cycle.name == "Loop"
        assert sm.slow_down.name == "Slow down"
        assert sm.stop.name == "stop"
        assert sm.go.name == "go"

    def test_multiple_ids_from_the_same_event_will_be_converted_to_multiple_events(self):
        class TrafficLightMachine(StateMachine):
            "A traffic light machine"

            green = State(initial=True)
            yellow = State()
            red = State()

            green.to(yellow, event=Event("cycle slowdown", name="Will be ignored"))
            yellow.to(red, event=Event("cycle stop", name="Will be ignored"))
            red.to(green, event=Event("cycle go", name="Will be ignored"))

            def on_cycle(self, event_data, event: str):
                assert event_data.event == event
                return (
                    f"Running {event} from {event_data.transition.source.id} to "
                    f"{event_data.transition.target.id}"
                )

        sm = TrafficLightMachine()

        assert sm.slowdown.name == "Slowdown"
        assert sm.stop.name == "Stop"
        assert sm.go.name == "Go"

        assert sm.send("cycle") == "Running cycle from green to yellow"
        assert sm.send("cycle") == "Running cycle from yellow to red"
        assert sm.send("cycle") == "Running cycle from red to green"

    def test_allow_registering_callbacks_using_decorator(self):
        class TrafficLightMachine(StateMachine):
            "A traffic light machine"

            green = State(initial=True)
            yellow = State()
            red = State()

            cycle = Event(
                green.to(yellow, event="slow_down")
                | yellow.to(red, event=["stop"])
                | red.to(green, event=["go"]),
                name="Loop",
            )

            @cycle.on
            def do_cycle(self, event_data, event: str):
                assert event_data.event == event
                return (
                    f"Running {event} from {event_data.transition.source.id} to "
                    f"{event_data.transition.target.id}"
                )

        sm = TrafficLightMachine()

        assert sm.send("cycle") == "Running cycle from green to yellow"

    def test_raise_registering_callbacks_using_decorator_if_no_transitions(self):
        with pytest.raises(InvalidDefinition, match="event with no transitions"):

            class TrafficLightMachine(StateMachine):
                "A traffic light machine"

                green = State(initial=True)
                yellow = State()
                red = State()

                cycle = Event(name="Loop")
                slow_down = Event()
                green.to(yellow, event=[cycle, slow_down])
                yellow.to(red, event=[cycle, "stop"])
                red.to(green, event=[cycle, "go"])

                @cycle.on
                def do_cycle(self, event_data, event: str):
                    assert event_data.event == event
                    return (
                        f"Running {event} from {event_data.transition.source.id} to "
                        f"{event_data.transition.target.id}"
                    )

    def test_allow_using_events_as_commands(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State()

            created.to(started, event=Event("launch_rocket"))

        sm = StartMachine()
        event = next(iter(sm.events))

        event()  # events on an instance machine are "bounded events"

        assert sm.started.is_active

    def test_event_commands_fail_when_unbound_to_instance(self):
        class StartMachine(StateMachine):
            created = State(initial=True)
            started = State()

            created.to(started, event=Event("launch_rocket"))

        event = next(iter(StartMachine.events))
        with pytest.raises(RuntimeError):
            event()
