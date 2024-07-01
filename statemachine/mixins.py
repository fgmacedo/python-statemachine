from . import registry
from .i18n import _


class MachineMixin:
    """This mixing allows a model to automatically instantiate and assign an
    ``StateMachine``.
    """

    state_field_name: str = "state"
    """The model's state field name that will hold the state value."""

    state_machine_name: "str | None" = None
    """A fully qualified name of the class, where it can be imported."""

    state_machine_attr: str = "statemachine"
    """Name of the model's attribute that will hold the machine instance."""

    bind_events_as_methods: bool = False
    """If ``True`` the state machine events triggers will be bound to the model as methods."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.state_machine_name:
            raise ValueError(
                _("{!r} is not a valid state machine name.").format(self.state_machine_name)
            )
        machine_cls = registry.get_machine_cls(self.state_machine_name)
        sm = machine_cls(self, state_field=self.state_field_name)
        setattr(
            self,
            self.state_machine_attr,
            sm,
        )
        if self.bind_events_as_methods:
            sm.bind_events_to(self)
