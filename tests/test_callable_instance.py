# coding: utf-8
from __future__ import absolute_import, unicode_literals

import mock

from statemachine.statemachine import CallableInstance


def test_callable_should_override_kwargs():
    target = mock.MagicMock(wil_be_overrided=1, will_be_proxied=2, z='text')
    proxy = CallableInstance(target, func=target.a_func, wil_be_overrided=3)

    assert proxy.wil_be_overrided == 3
    assert proxy.will_be_proxied == 2
    assert proxy.z == 'text'

    proxy(4, 5, k=6)

    target.a_func.assert_called_once_with(4, 5, k=6)
