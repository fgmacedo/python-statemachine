from statemachine import State
from statemachine import StateChart


class Fellowship(StateChart):
    class positions(State.Parallel):
        class frodo(State.Compound):
            shire_f = State(initial=True)
            mordor_f = State(final=True)

            journey = shire_f.to(mordor_f)

        class sam(State.Compound):
            shire_s = State(initial=True)
            mordor_s = State(final=True)

            # Sam follows Frodo: eventless, guarded by In('mordor_f')
            shire_s.to(mordor_s, cond="In('mordor_f')")
