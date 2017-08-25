# coding: utf-8
from __future__ import absolute_import, unicode_literals


def test_should_register_a_state_machine():
    from statemachine import StateMachine, State, registry

    class CampaignMachine(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True)
        producing = State('Being produced')

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)

    assert 'CampaignMachine' in registry._REGISTRY
    assert registry.get_machine_cls('CampaignMachine') == CampaignMachine
