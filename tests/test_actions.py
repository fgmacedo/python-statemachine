# coding: utf-8
import mock

from statemachine import StateMachine, State


class TestActions:
    def test_should_return_all_before_results(self):

        spy = mock.Mock(side_effect=lambda x: x)

        class Machine(StateMachine):

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

            # validations and conditions

            def validation_1(self):
                # this method may raise an exception
                return spy("validation_1")

            def validation_2(self):
                # this method may raise an exception
                return spy("validation_2")

            def condition_1(self):
                spy("condition_1")
                return True

            def condition_2(self):
                spy("condition_2")
                return True

            def unless_1(self):
                spy("unless_1")
                return False

            def unless_2(self):
                spy("unless_2")
                return False

            # generics state

            def on_enter_state(self):
                return spy("on_enter_state")

            def on_exit_state(self):
                return spy("on_exit_state")

            # generics transition

            def before_transition(self):
                return spy("before_transition")

            def after_transition(self):
                return spy("after_transition")

            # before / after specific

            def on_execute_1(self):
                return spy("on_execute_1")

            def on_execute_2(self):
                return spy("on_execute_2")

            def before_go_inline_1(self):
                return spy("before_go_inline_1")

            def before_go_inline_2(self):
                return spy("before_go_inline_2")

            def before_go(self):
                return spy("before_go")

            def on_go(self):
                return spy("on_go")

            def after_go_inline_1(self):
                return spy("after_go_inline_1")

            def after_go_inline_2(self):
                return spy("after_go_inline_2")

            def after_go(self):
                return spy("after_go")

            # enter / exit specific

            def on_enter_initial(self):
                return spy("on_enter_initial")

            def on_exit_initial(self):
                return spy("on_exit_initial")

            def on_enter_final(self):
                return spy("on_enter_final")

            def on_exit_final(self):
                "hopefully this will not be called"
                return spy("on_exit_final")

        machine = Machine()

        result = machine.go()
        assert result == [
            "before_transition",
            "before_go_inline_1",
            "before_go_inline_2",
            "on_execute_1",
            "on_execute_2",
            "before_go",
            "on_go",
        ]

        # ensure correct call order
        assert spy.call_args_list == [
            mock.call("on_enter_state"),
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
            mock.call("on_execute_1"),
            mock.call("on_execute_2"),
            mock.call("before_go"),
            mock.call("on_go"),
            mock.call("on_exit_state"),
            mock.call("on_exit_initial"),
            mock.call("on_enter_state"),
            mock.call("on_enter_final"),
            mock.call("after_go_inline_1"),
            mock.call("after_go_inline_2"),
            mock.call("after_go"),
            mock.call("after_transition"),
        ]
