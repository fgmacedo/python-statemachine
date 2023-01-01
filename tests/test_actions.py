# coding: utf-8

import mock


class TestActions:
    def test_should_return_all_before_results(self, AllActionsMachine):

        machine = AllActionsMachine()
        spy = machine.spy

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
