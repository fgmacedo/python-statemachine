from statemachine import StateMachine
from statemachine.states import States

from .models import WorkflowSteps


class WorfklowStateMachine(StateMachine):
    _ = States.from_enum(WorkflowSteps, initial=WorkflowSteps.DRAFT, final=WorkflowSteps.PUBLISHED)

    publish = _.draft.to(_.published, cond="is_active")
    notify_user = _.draft.to.itself(internal=True, cond="has_user")

    def has_user(self):
        return bool(self.model.user)
