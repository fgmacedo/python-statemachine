"""
All actions machine
-------------------

A StateMachine that exercices all possible :ref:`Actions` and :ref:`Guards`.

"""

import mock

from statemachine import StateMachine, State


class AllActionsMachine(StateMachine):

    initial = State("Initial", initial=True)
    final = State("Final", final=True)

    go = initial.to(
        final,
        validators=["validation_1", "validation_2"],
        conditions=["condition_1", "condition_2"],
        unless=["unless_1", "unless_2"],
        on_execute=["on_execute_1", "on_execute_2"],
        before=["before_go_inline_1", "before_go_inline_2"],
        after=["after_go_inline_1", "after_go_inline_2"],
    )

    def __init__(self, *args, **kwargs):
        self.spy = mock.Mock(side_effect=lambda x: x)
        super(AllActionsMachine, self).__init__(*args, **kwargs)

    # validations and conditions

    def validation_1(self):
        # this method may raise an exception
        return self.spy("validation_1")

    def validation_2(self):
        # this method may raise an exception
        return self.spy("validation_2")

    def condition_1(self):
        self.spy("condition_1")
        return True

    def condition_2(self):
        self.spy("condition_2")
        return True

    def unless_1(self):
        self.spy("unless_1")
        return False

    def unless_2(self):
        self.spy("unless_2")
        return False

    # generics state

    def on_enter_state(self):
        return self.spy("on_enter_state")

    def on_exit_state(self):
        return self.spy("on_exit_state")

    # generics transition

    def before_transition(self):
        return self.spy("before_transition")

    def after_transition(self):
        return self.spy("after_transition")

    # before / after specific

    def on_execute_1(self):
        return self.spy("on_execute_1")

    def on_execute_2(self):
        return self.spy("on_execute_2")

    def before_go_inline_1(self):
        return self.spy("before_go_inline_1")

    def before_go_inline_2(self):
        return self.spy("before_go_inline_2")

    def before_go(self):
        return self.spy("before_go")

    def on_go(self):
        return self.spy("on_go")

    def after_go_inline_1(self):
        return self.spy("after_go_inline_1")

    def after_go_inline_2(self):
        return self.spy("after_go_inline_2")

    def after_go(self):
        return self.spy("after_go")

    # enter / exit specific

    def on_enter_initial(self):
        return self.spy("on_enter_initial")

    def on_exit_initial(self):
        return self.spy("on_exit_initial")

    def on_enter_final(self):
        return self.spy("on_enter_final")

    def on_exit_final(self):
        "hopefully this will not be called"
        return self.spy("on_exit_final")
