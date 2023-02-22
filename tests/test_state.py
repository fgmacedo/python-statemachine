from statemachine import State
from statemachine import StateMachine


class TestState:
    def test_name_derived_from_id(self):
        class SM(StateMachine):
            pending = State(initial=True)
            waiting_approval = State()
            approved = State(final=True)

            start = pending.to(waiting_approval)
            approve = waiting_approval.to(approved)

        assert SM.pending.name == "Pending"
        assert SM.waiting_approval.name == "Waiting approval"
        assert SM.approved.name == "Approved"
