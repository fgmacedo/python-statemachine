# coding: utf-8
from __future__ import absolute_import, unicode_literals

import mock
import pytest


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


@pytest.fixture()
def django_module_loading():
    import sys
    if 'django' not in sys.modules:
        django = mock.MagicMock()
        module_loading = mock.MagicMock()
        sys.modules['django'] = django
        sys.modules['django.utils.module_loading'] = module_loading
        yield module_loading
        del sys.modules['django']
        del sys.modules['django.utils.module_loading']


def test_load_modules_should_call_autodiscover_modules(django_module_loading):
    from statemachine.registry import load_modules

    # given
    modules = ['a', 'c', 'statemachine', 'statemachines']

    # when
    load_modules(modules)

    # then
    django_module_loading.autodiscover_modules.assert_has_calls(
        mock.call(m) for m in modules
    )
