from unittest import mock

import pytest


@pytest.fixture()
def django_autodiscover_modules():
    auto_discover_modules = mock.MagicMock()

    with mock.patch("statemachine.registry.autodiscover_modules", new=auto_discover_modules):
        yield auto_discover_modules


def test_should_register_a_state_machine(caplog, django_autodiscover_modules):
    from statemachine import State
    from statemachine import StateMachine
    from statemachine import registry

    class CampaignMachine(StateMachine):
        "A workflow machine"

        draft = State(initial=True)
        producing = State()

        add_job = draft.to(draft) | producing.to(producing)
        produce = draft.to(producing)

    assert "CampaignMachine" in registry._REGISTRY
    assert registry.get_machine_cls("tests.test_registry.CampaignMachine") == CampaignMachine

    with pytest.warns(DeprecationWarning):
        assert registry.get_machine_cls("CampaignMachine") == CampaignMachine


def test_load_modules_should_call_autodiscover_modules(django_autodiscover_modules):
    from statemachine.registry import load_modules

    # given
    modules = ["a", "c", "statemachine", "statemachines"]

    # when
    load_modules(modules)

    # then
    django_autodiscover_modules.assert_has_calls(mock.call(m) for m in modules)
