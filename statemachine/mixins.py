# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from typing import Text

try:
    from django.utils.translation import ugettext as _
except Exception:

    def _(text):
        return text


from . import registry


class MachineMixin(object):
    """This mixing allows a model to automatically instantiate and assign an
    ``StateMachine``.
    """

    state_field_name = "state"  # type: Text
    """The model's state field name that will hold the state value."""

    state_machine_name = None  # type: Text
    """A fully qualified name of the class, where it can be imported."""

    state_machine_attr = "statemachine"  # type: Text
    """Name of the model's attribute that will hold the machine instance."""

    def __init__(self, *args, **kwargs):
        super(MachineMixin, self).__init__(*args, **kwargs)
        if not self.state_machine_name:
            raise ValueError(
                _("{!r} is not a valid state machine name.").format(
                    self.state_machine_name
                )
            )
        machine_cls = registry.get_machine_cls(self.state_machine_name)
        setattr(
            self,
            self.state_machine_attr,
            machine_cls(self, state_field=self.state_field_name),
        )
