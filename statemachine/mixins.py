from . import registry
from .i18n import _


class MachineMixin:
    """This mixing allows a model to automatically instantiate and assign an
    ``StateMachine``.
    """

    state_field_name = "state"  # type: str
    """The model's state field name that will hold the state value."""

    state_machine_name = None  # type: str
    """A fully qualified name of the class, where it can be imported."""

    state_machine_attr = "statemachine"  # type: str
    """Name of the model's attribute that will hold the machine instance."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
