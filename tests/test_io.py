"""Tests for statemachine.io module (dictionary-based state machine definitions)."""

from statemachine.io import _parse_history
from statemachine.io import create_machine_class_from_definition


class TestParseHistory:
    def test_history_without_transitions(self):
        """History state with no 'on' or 'transitions' keys."""
        states_instances, events_definitions = _parse_history({"h1": {"deep": False}})
        assert "h1" in states_instances
        assert states_instances["h1"].deep is False
        assert events_definitions == {}

    def test_history_with_on_only(self):
        """History state with 'on' events but no 'transitions' key."""
        states_instances, events_definitions = _parse_history(
            {"h1": {"deep": True, "on": {"restore": [{"target": "s1"}]}}}
        )
        assert "h1" in states_instances
        assert "h1" in events_definitions
        assert "restore" in events_definitions["h1"]


class TestCreateMachineWithEventNameConcat:
    def test_transition_with_both_parent_and_own_event_name(self):
        """Transition inside 'on' dict that also has its own 'event' key concatenates names."""
        sm_cls = create_machine_class_from_definition(
            "TestMachine",
            states={
                "s1": {
                    "initial": True,
                    "on": {
                        "parent_evt": [
                            {"target": "s2", "event": "sub_evt"},
                        ],
                    },
                },
                "s2": {"final": True},
            },
        )
        sm = sm_cls()
        # The concatenated event name "parent_evt sub_evt" gets split into two events
        event_ids = sorted(e.id for e in sm.events)
        assert "parent_evt" in event_ids
        assert "sub_evt" in event_ids
