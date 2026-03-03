from statemachine import State
from statemachine import StateChart


class WarOfTheRing(StateChart):
    class war(State.Parallel):
        class frodos_quest(State.Compound):
            shire = State(initial=True)
            mordor = State()
            mount_doom = State(final=True)

            journey = shire.to(mordor)
            destroy_ring = mordor.to(mount_doom)

        class aragorns_path(State.Compound):
            ranger = State(initial=True)
            king = State(final=True)

            coronation = ranger.to(king)

        class gandalfs_defense(State.Compound):
            rohan = State(initial=True)
            gondor = State(final=True)

            ride_to_gondor = rohan.to(gondor)
