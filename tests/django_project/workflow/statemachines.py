from statemachine import StateMachine
from statemachine.states import States

from .models import WorkflowSteps


class WorfklowStateMachine(StateMachine):
    _ = States.from_enum(WorkflowSteps, initial=WorkflowSteps.DRAFT, final=WorkflowSteps.PUBLISHED)

    publish = _.DRAFT.to(_.PUBLISHED, cond="is_active")
    notify_user = _.DRAFT.to.itself(internal=True, cond="has_user")

    def has_user(self):
        return bool(self.model.user)
