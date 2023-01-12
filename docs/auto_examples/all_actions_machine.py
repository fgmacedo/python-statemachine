"""
All actions machine
===================

A StateMachine that exercices all possible :ref:`Actions` and :ref:`Guards`.

"""
import mock

from statemachine import State
from statemachine import StateMachine


class AllActionsMachine(StateMachine):

    initial = State("Initial", initial=True)
    final = State("Final", final=True)

    go = initial.to(
        final,
        validators=["validation_1", "validation_2"],
        cond=["condition_1", "condition_2"],
        unless=["unless_1", "unless_2"],
        on=["on_inline_1", "on_inline_2"],
        before=["before_go_inline_1", "before_go_inline_2"],
        after=["after_go_inline_1", "after_go_inline_2"],
    )

    def __init__(self, *args, **kwargs):
        self.spy = mock.Mock(side_effect=lambda x: x)
        super(AllActionsMachine, self).__init__(*args, **kwargs)

    # validators and guards

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

    def on_transition(self):
        return self.spy("on_transition")

    def after_transition(self):
        return self.spy("after_transition")

    # before / after specific

    @go.before
    def before_go_decor(self):
        return self.spy("before_go_decor")

    def before_go_inline_1(self):
        return self.spy("before_go_inline_1")

    def before_go_inline_2(self):
        return self.spy("before_go_inline_2")

    def before_go(self):
        return self.spy("before_go")

    @go.on
    def go_on_decor(self):
        return self.spy("go_on_decor")

    def on_inline_1(self):
        return self.spy("on_inline_1")

    def on_inline_2(self):
        return self.spy("on_inline_2")

    def on_go(self):
        return self.spy("on_go")

    @go.after
    def after_go_decor(self):
        return self.spy("after_go_decor")

    def after_go_inline_1(self):
        return self.spy("after_go_inline_1")

    def after_go_inline_2(self):
        return self.spy("after_go_inline_2")

    def after_go(self):
        return self.spy("after_go")

    # enter / exit specific

    @initial.enter
    def enter_initial_decor(self):
        return self.spy("enter_initial_decor")

    def on_enter_initial(self):
        return self.spy("on_enter_initial")

    @initial.exit
    def exit_initial_decor(self):
        return self.spy("exit_initial_decor")

    def on_exit_initial(self):
        return self.spy("on_exit_initial")

    def on_enter_final(self):
        return self.spy("on_enter_final")

    def on_exit_final(self):
        "hopefully this will not be called"
        return self.spy("on_exit_final")


# %%
# Testing
# -------

machine = AllActionsMachine()
spy = machine.spy


# %%
# Only before/on actions have their result collected.

result = machine.go()
assert result == [
    "before_transition",
    "before_go_inline_1",
    "before_go_inline_2",
    "before_go_decor",
    "before_go",
    "on_transition",
    "on_inline_1",
    "on_inline_2",
    "go_on_decor",
    "on_go",
]

# %%
# Checking the method resolution order

assert spy.call_args_list == [
    mock.call("on_enter_state"),
    mock.call("enter_initial_decor"),
    mock.call("on_enter_initial"),
    mock.call("validation_1"),
    mock.call("validation_2"),
    mock.call("condition_1"),
    mock.call("condition_2"),
    mock.call("unless_1"),
    mock.call("unless_2"),
    mock.call("before_transition"),
    mock.call("before_go_inline_1"),
    mock.call("before_go_inline_2"),
    mock.call("before_go_decor"),
    mock.call("before_go"),
    mock.call("on_exit_state"),
    mock.call("exit_initial_decor"),
    mock.call("on_exit_initial"),
    mock.call("on_transition"),
    mock.call("on_inline_1"),
    mock.call("on_inline_2"),
    mock.call("go_on_decor"),
    mock.call("on_go"),
    mock.call("on_enter_state"),
    mock.call("on_enter_final"),
    mock.call("after_go_inline_1"),
    mock.call("after_go_inline_2"),
    mock.call("after_go_decor"),
    mock.call("after_go"),
    mock.call("after_transition"),
]
