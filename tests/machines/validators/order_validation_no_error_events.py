from statemachine import State
from statemachine import StateChart


class OrderValidationNoErrorEvents(StateChart):
    """Same machine but with catch_errors_as_events=False."""

    catch_errors_as_events = False

    pending = State(initial=True)
    confirmed = State()
    cancelled = State(final=True)

    confirm = pending.to(confirmed, validators="check_stock")
    cancel = confirmed.to(cancelled)

    def check_stock(self, quantity=0, **kwargs):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
