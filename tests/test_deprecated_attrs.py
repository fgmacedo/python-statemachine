class TestDeprecatedAttrs:
    def test_event_identifier(self, campaign_machine):
        sm = campaign_machine()
        assert [e.identifier for e in sm.events] == [e.name for e in sm.events]

    def test_state_identifier(self, campaign_machine):
        sm = campaign_machine()
        assert sm.draft.identifier == sm.draft.id

    def test_transitions_list(self, campaign_machine):
        sm = campaign_machine()
        assert [t.identifier for t in sm.transitions] == [e.name for e in sm.events]

    def test_transition_identifier(self, campaign_machine):
        sm = campaign_machine()
        assert [t.identifier for t in sm.draft.transitions] == ["add_job", "produce"]

    def test_allowed_transitions(self, campaign_machine):
        sm = campaign_machine()
        assert sm.allowed_transitions == sm.allowed_events

    def test_class_attr_transitions(self, campaign_machine):
        assert sorted(t.identifier for t in campaign_machine.transitions) == sorted(
            ["add_job", "produce", "deliver"]
        )

    def test_run(self, campaign_machine):
        sm = campaign_machine()
        sm.run("produce")
        assert sm.producing.is_active

    def test_is_stateid_check_property(self, campaign_machine):
        sm = campaign_machine()
        assert sm.is_draft == sm.draft.is_active
        sm.produce()
        assert sm.is_producing == sm.producing.is_active
