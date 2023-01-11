"""
Guess the number machine
========================

An StateMachine for the well know game.

Well leave the machine imagine a number and also play the game. Why not?

"""
import random

from statemachine import State
from statemachine import StateMachine


class GuessTheNumberMachine(StateMachine):

    start = State("Start", initial=True)
    low = State("Low")
    high = State("High")
    won = State("Won", final=True)
    lose = State("Lose", final=True)

    guess = (
        lose.from_(low, high, cond="max_guesses_reached")
        | won.from_(low, high, cond="guess_is_equal")
        | low.from_(low, high, start, cond="guess_is_lower")
        | high.from_(low, high, start, cond="guess_is_higher")
    )

    def __init__(self, max_attempts=5, lower=1, higher=5, seed=42):
        self.max_attempts = max_attempts
        self.lower = lower
        self.higher = higher
        self.guesses = 0

        # lets play a not so random game, or our tests will be crazy
        random.seed(seed)
        self.number = random.randint(self.lower, self.higher)
        super(GuessTheNumberMachine, self).__init__()

    def max_guesses_reached(self):
        return self.guesses >= self.max_attempts

    def before_guess(self, number):
        self.guesses += 1
        print("You guess is {}...".format(number))

    def guess_is_lower(self, number):
        return number < self.number

    def guess_is_higher(self, number):
        return number > self.number

    def guess_is_equal(self, number):
        return self.number == number

    def on_enter_start(self):
        print("(psss.. don't tell anyone the number is {})".format(self.number))
        print(
            "I'm thinking of a number between {} and {}. Can you guess what it is?".format(
                self.lower, self.higher
            )
        )

    def on_enter_low(self):
        print("Too low. Try again.")

    def on_enter_high(self):
        print("Too high. Try again.")

    def on_enter_won(self):
        print(
            "Congratulations, you guessed the number in {} guesses!".format(
                self.guesses
            )
        )

    def on_enter_lose(self):
        print("Oh, no! You've spent all your {} attempts!".format(self.guesses))


# %%
# Playing
# -------
#

sm = GuessTheNumberMachine(seed=103)

# %%

sm.guess(random.randint(1, 5))

# %%

sm

# %%

sm.guess(random.randint(1, 5))

# %%

sm.guess(random.randint(1, 5))


sm

# %%

# %%

sm.guess(random.randint(1, 5))

# %%

sm.guess(random.randint(1, 5))

# %%

sm

# %%

try:
    sm.guess(random.randint(1, 5))
except Exception as e:
    print(e)
