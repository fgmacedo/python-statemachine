from statemachine.callbacks import CallbackMeta


class TestActions:
    def test_should_return_all_before_results(self, AllActionsMachine):
        import tests.examples.all_actions_machine  # noqa

    def test_should_allow_actions_on_the_model(self):
        # just importing, as the example has assertions
        import tests.examples.order_control_rich_model_machine  # noqa

    def test_should_should_compute_callbacks_meta_list(self, campaign_machine):
        sm = campaign_machine()
        assert list(sm.draft.enter) == [
            CallbackMeta("on_enter_state", suppress_errors=True),
            CallbackMeta("on_enter_draft", suppress_errors=True),
        ]
        assert list(sm.draft.exit) == [
            CallbackMeta("on_exit_state", suppress_errors=True),
            CallbackMeta("on_exit_draft", suppress_errors=True),
        ]
