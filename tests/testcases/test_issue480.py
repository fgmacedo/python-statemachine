"""

### Issue 480

A StateMachine that exercises the example given on issue
#[480](https://github.com/fgmacedo/python-statemachine/issues/480).

Should be possible to trigger an event on the initial state activation handler.
"""

from unittest.mock import MagicMock
from unittest.mock import call

from statemachine import State
from statemachine import StateMachine


class MyStateMachine(StateMachine):
    state_1 = State(initial=True)
    state_2 = State(final=True)

    trans_1 = state_1.to(state_2)

    def __init__(self):
        self.mock = MagicMock()
        super().__init__()

    def on_enter_state_1(self):
        self.mock("on_enter_state_1")
        self.long_running_task()

    def on_exit_state_1(self):
        self.mock("on_exit_state_1")

    def on_enter_state_2(self):
        self.mock("on_enter_state_2")

    def long_running_task(self):
        self.mock("long_running_task_started")
        self.trans_1()
        self.mock("long_running_task_ended")


def test_initial_state_activation_handler():
    sm = MyStateMachine()

    expected_calls = [
        call("on_enter_state_1"),
        call("long_running_task_started"),
        call("long_running_task_ended"),
        call("on_exit_state_1"),
        call("on_enter_state_2"),
    ]

    assert sm.mock.mock_calls == expected_calls
    assert sm.current_state == sm.state_2
