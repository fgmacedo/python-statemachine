from statemachine import StateMachine

"""
Test cases as defined by W3C SCXML Test Suite
"""


def test_usecase(testcase_path, sm_class):
    # sm._graph().write_png(f"{testcase_path.name}.png")
    sm = sm_class()
    assert isinstance(sm, StateMachine)
    assert sm.current_state.id == "pass"
