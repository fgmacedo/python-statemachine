from statemachine.callbacks import CallbackGroup
from statemachine.callbacks import CallbackSpec


class TestActions:
    def test_should_return_all_before_results(self, AllActionsMachine):
        import tests.examples.all_actions_machine  # noqa

    def test_should_allow_actions_on_the_model(self):
        # just importing, as the example has assertions
        import tests.examples.order_control_rich_model_machine  # noqa

    def test_should_should_compute_callbacks_meta_list(self, campaign_machine):
        sm = campaign_machine()
        assert list(sm.draft.enter) == [
            CallbackSpec("on_enter_state", CallbackGroup.ENTER, is_convention=True),
            CallbackSpec("on_enter_draft", CallbackGroup.ENTER, is_convention=True),
        ]
        assert list(sm.draft.exit) == [
            CallbackSpec("on_exit_state", CallbackGroup.EXIT, is_convention=True),
            CallbackSpec("on_exit_draft", CallbackGroup.EXIT, is_convention=True),
        ]
