# coding: utf-8


class TestActions:
    def test_should_return_all_before_results(self, AllActionsMachine):
        import tests.examples.all_actions_machine  # noqa

    def test_should_allow_actions_on_the_model(self):
        # just importing, as the example has assertions
        import tests.examples.order_control_rich_model_machine  # noqa

    def test_should_ignore_preconfigured_callbacks_not_present_(self, campaign_machine):
        sm = campaign_machine()
        assert sm.draft.enter.items == []
        assert sm.draft.exit.items == []
