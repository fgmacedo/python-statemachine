import pytest

from statemachine import State


@pytest.fixture()
def microwave_cls():
    from tests.examples.microwave_inheritance_machine import MicroWave

    return MicroWave


def assert_state(s, name, initial=False, final=False, parallel=False, substates=None):
    if substates is None:
        substates = []

    assert isinstance(s, State)
    assert s.name == name
    assert s.initial is initial
    assert s.final is final
    assert s.parallel is parallel
    assert isinstance(s, State)
    assert set(s.substates) == set(substates)


class TestNestedSyntax:
    def test_capture_constructor_arguments(self, microwave_cls):
        sm = microwave_cls()

        assert_state(
            sm.oven,
            "Microwave oven",
            parallel=True,
            substates=[sm.oven.engine, sm.oven.door],
        )
        assert_state(
            sm.oven.engine,
            "Engine",
            initial=False,
            substates=[sm.oven.engine.on, sm.oven.engine.off],
        )
        assert_state(sm.oven.engine.off, "Off", initial=True)
        assert_state(
            sm.oven.engine.on,
            "On",
            substates=[sm.oven.engine.on.idle, sm.oven.engine.on.cooking],
        )
        assert_state(
            sm.oven.door,
            "Door",
            initial=False,
            substates=[sm.oven.door.closed, sm.oven.door.open],
        )
        assert_state(sm.oven.door.closed, "Closed", initial=True)
        assert_state(sm.oven.door.open, "Open")

    def test_list_children_states(self, microwave_cls):
        sm = microwave_cls()
        assert [s.id for s in sm.oven.engine.substates] == ["off", "on"]

    def test_list_events(self, microwave_cls):
        sm = microwave_cls()
        assert [e.name for e in sm.events] == [
            "turn_on",
            "turn_off",
            "door_open",
            "door_close",
        ]
