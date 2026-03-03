from statemachine import State
from statemachine import StateChart


class CampaignMachine(StateChart):
    "A workflow machine"

    draft = State(initial=True)
    producing = State("Being produced")
    closed = State(final=True)

    add_job = draft.to(draft) | producing.to(producing)
    produce = draft.to(producing)
    deliver = producing.to(closed)
