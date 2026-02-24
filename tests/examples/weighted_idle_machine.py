"""

------------------------------
Weighted idle animation machine
------------------------------

This example demonstrates how to use ``weighted_transitions`` to create probabilistic
idle animations for a game character. Each time the ``idle`` event fires, the character
randomly picks an animation based on relative weights.

"""

from statemachine.contrib.weighted import weighted_transitions

from statemachine import State
from statemachine import StateChart


class WeightedIdleMachine(StateChart):
    """A game character with weighted idle animations.

    When idle, the character randomly picks an animation based on weights:
    - 70% chance: shift weight from foot to foot
    - 20% chance: adjust hair
    - 10% chance: bang shield
    """

    standing = State(initial=True)
    shift_weight = State()
    adjust_hair = State()
    bang_shield = State()

    idle = weighted_transitions(
        standing,
        (shift_weight, 70),
        (adjust_hair, 20),
        (bang_shield, 10),
        seed=42,
    )

    finish = shift_weight.to(standing) | adjust_hair.to(standing) | bang_shield.to(standing)
