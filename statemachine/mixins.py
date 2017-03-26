# coding: utf-8
from __future__ import unicode_literals, absolute_import

try:
    from django.utils.translation import ugettext as _
except Exception:
    def _(text):
        return text
from . import registry


class MachineMixin(object):
    state_field_name = 'state'
    state_machine_name = None
    state_machine_attr = 'statemachine'

    def __init__(self, *args, **kwargs):
        super(MachineMixin, self).__init__(*args, **kwargs)
        if not self.state_machine_name:
            raise ValueError(_("{!r} is not a valid state machine name.").format(
                self.state_machine_name))
        machine_cls = registry.get_machine_cls(self.state_machine_name)
        setattr(
            self,
            self.state_machine_attr,
            machine_cls(self, state_field=self.state_field_name)
        )
