from statemachine import State
from statemachine import StateMachine


class WorfklowStateMachine(StateMachine):
    draft = State(initial=True)
    published = State()

    publish = draft.to(published, cond="is_active")
    notify_user = draft.to.itself(internal=True, cond="has_user")

    def has_user(self):
        return bool(self.model.user)
