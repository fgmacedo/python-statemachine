def test_nested_sm():
    from tests.examples.microwave_inheritance_machine import MicroWave

    sm = MicroWave()
    assert sm.current_state.id == "oven"
