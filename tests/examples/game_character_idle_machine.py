"""
Example: Game Character Idle Animations with Probabilistic Transitions
======================================================================

This example demonstrates how to use weighted transitions to create
realistic idle animations for a game character. The character will randomly
choose different idle animations based on weighted probabilities.

The character has a standing state, and when idle, will probabilistically
transition to different animations:
- 70% chance: Shift weight from one foot to the other
- 20% chance: Run hand through hair
- 10% chance: Bang sword against shield

After performing an idle animation, the character returns to standing.
"""

from statemachine import State, StateMachine


class GameCharacter(StateMachine):
    """A game character with weighted idle animations."""

    # States
    standing = State("Standing", initial=True)
    shift_weight = State("Shifting Weight")
    adjust_hair = State("Adjusting Hair")
    bang_shield = State("Banging Shield")

    # Weighted idle transitions - 70/20/10 split
    idle = (
        standing.to(shift_weight, event="idle", weight=70)
        | standing.to(adjust_hair, event="idle", weight=20)
        | standing.to(bang_shield, event="idle", weight=10)
    )

    # Return to standing after each animation
    finish = (
        shift_weight.to(standing)
        | adjust_hair.to(standing)
        | bang_shield.to(standing)
    )

    def __init__(self, random_seed=None):
        """Initialize the character.

        Args:
            random_seed: Optional seed for deterministic behavior in tests.
        """
        self.animation_log = []
        super().__init__(random_seed=random_seed)

    def on_enter_shift_weight(self):
        """Called when entering shift_weight state."""
        self.animation_log.append("shift_weight")
        print("  → Character shifts weight from one foot to the other")

    def on_enter_adjust_hair(self):
        """Called when entering adjust_hair state."""
        self.animation_log.append("adjust_hair")
        print("  → Character runs hand through hair")

    def on_enter_bang_shield(self):
        """Called when entering bang_shield state."""
        self.animation_log.append("bang_shield")
        print("  → Character bangs sword against shield")


def main():
    """Run the example."""
    print("Game Character Idle Animations Example")
    print("=" * 50)
    print()

    # Create a character with a seed for reproducible demonstration
    character = GameCharacter(random_seed=42)

    print("Current state:", character.current_state.name)
    print()

    # Trigger idle animations 10 times
    print("Triggering 10 idle animations:")
    print()

    for i in range(1000):
        print(f"Idle #{i+1}:")
        character.idle()
        character.finish()

    print()
    print("Animation summary:")
    from collections import Counter

    counts = Counter(character.animation_log)
    for anim, count in counts.most_common():
        percentage = (count / len(character.animation_log)) * 100
        print(f"  {anim}: {count} times ({percentage:.0f}%)")

    print()
    print("Expected distribution: shift_weight ~70%, adjust_hair ~20%, bang_shield ~10%")


if __name__ == "__main__":
    main()

