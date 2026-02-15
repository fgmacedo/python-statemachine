(weighted-transitions)=

# Weighted transitions

```{versionadded} 3.0.0
```

The `weighted_transitions` utility lets you define **probabilistic transitions** — where
each transition from a state has a relative weight that determines how likely it is to be
selected when the event fires.

This is a contrib module that works entirely through the existing {ref}`guards` system.
No engine modifications are needed.

## Installation

The module is included in the `python-statemachine` package. Import it from the contrib
namespace:

```python
from statemachine.contrib.weighted import weighted_transitions

# Only needed when passing transition kwargs (cond, on, etc.)
from statemachine.contrib.weighted import to
```

## Basic usage

Pass a **source state** followed by `(target, weight)` tuples. The result is a regular
{ref}`TransitionList` that you assign to a class attribute as an event:

```{testsetup}

>>> from statemachine import State, StateChart
>>> from statemachine.contrib.weighted import to, weighted_transitions

```

```py
>>> class GameCharacter(StateChart):
...     standing = State(initial=True)
...     shift_weight = State()
...     adjust_hair = State()
...     bang_shield = State()
...
...     idle = weighted_transitions(
...         standing,
...         (shift_weight, 70),
...         (adjust_hair, 20),
...         (bang_shield, 10),
...         seed=42,
...     )
...
...     finish = (
...         shift_weight.to(standing)
...         | adjust_hair.to(standing)
...         | bang_shield.to(standing)
...     )

>>> sm = GameCharacter()
>>> sm.send("idle")
>>> any(
...     s in sm.configuration_values
...     for s in ("shift_weight", "adjust_hair", "bang_shield")
... )
True

```

When `idle` fires, the engine randomly selects one of the three transitions based on
their relative weights: 70% chance for `shift_weight`, 20% for `adjust_hair`,
10% for `bang_shield`.

## Weights

Weights can be any **positive number** — integers, floats, or a mix of both. They are
relative, not absolute percentages:

```python
# These are equivalent (same 70/20/10 ratio):
idle = weighted_transitions(
    standing,
    (shift_weight, 70),
    (adjust_hair, 20),
    (bang_shield, 10),
)

idle = weighted_transitions(
    standing,
    (shift_weight, 7),
    (adjust_hair, 2),
    (bang_shield, 1),
)

idle = weighted_transitions(
    standing,
    (shift_weight, 0.7),
    (adjust_hair, 0.2),
    (bang_shield, 0.1),
)
```

The tuple format `(target, weight)` follows the standard Python pattern used by
{py:func}`random.choices`.

## Reproducibility with `seed`

Pass a `seed` parameter for deterministic, reproducible sequences — useful for testing:

```python
go = weighted_transitions(
    s1,
    (s2, 50),
    (s3, 50),
    seed=42,  # same seed always produces the same sequence
)
```

```{note}
The seed initializes a per-group `random.Random` instance that is shared across all
instances of the same state machine class. This means the sequence is deterministic
for a given program execution, but different instances advance the same RNG.
```

## Per-transition options

Use the {func}`~statemachine.contrib.weighted.to` helper to pass transition keyword
arguments (``cond``, ``unless``, ``before``, ``on``, ``after``, …) as natural kwargs.
For simple destinations without extra options, a plain ``(target, weight)`` tuple is
enough — ``to()`` is only needed when you want to customize the transition:

```py
>>> class GuardedWeighted(StateChart):
...     idle = State(initial=True)
...     walk = State()
...     run = State()
...
...     move = weighted_transitions(
...         idle,
...         (walk, 70),
...         to(run, 30, cond="has_energy"),
...     )
...     stop = walk.to(idle) | run.to(idle)
...
...     has_energy = True

>>> sm = GuardedWeighted()

```

```{important}
**No fallback when a guard fails.** If the weighted selection picks a transition whose
guard evaluates to ``False``, the event fails — the engine does **not** silently fall back
to another transition. This preserves the probability semantics: a 70/30 split means
exactly that, not "70/30 unless the 30% is blocked, in which case always 100% for
the other".

This behavior follows {ref}`conditions` evaluation: the first transition whose **all**
conditions pass is executed.
```

## Combining with callbacks

All standard {ref}`actions` work with weighted events — `before`, `on`, `after` callbacks
and naming conventions like `on_<event>()`:

```python
class WithCallbacks(StateChart):
    s1 = State(initial=True)
    s2 = State()
    s3 = State()

    go = weighted_transitions(s1, (s2, 60), (s3, 40))
    back = s2.to(s1) | s3.to(s1)

    def on_go(self):
        print("go event fired!")

    def after_go(self):
        print("after go!")
```

## Multiple independent groups

Each call to `weighted_transitions()` creates an independent weighted group with its
own RNG. You can have multiple weighted events on the same state machine:

```python
class MultiGroup(StateChart):
    idle = State(initial=True)
    walk = State()
    run = State()
    wave = State()
    bow = State()

    move = weighted_transitions(idle, (walk, 70), (run, 30), seed=1)
    greet = weighted_transitions(idle, (wave, 80), (bow, 20), seed=2)
    back = walk.to(idle) | run.to(idle) | wave.to(idle) | bow.to(idle)
```

The `move` and `greet` events use separate RNGs and don't interfere with each other.

## Validation

`weighted_transitions()` validates inputs at class definition time:

- The first argument must be a `State` (the source).
- Each destination must be a `(target_state, weight)` or
  `(target_state, weight, kwargs_dict)` tuple.
- Weights must be positive numbers (`int` or `float`).
- At least one destination is required.

```py
>>> weighted_transitions(State(initial=True))
Traceback (most recent call last):
    ...
ValueError: weighted_transitions() requires at least one (target, weight) destination

>>> s1, s2 = State(initial=True), State()
>>> weighted_transitions(s1, (s2, -5))
Traceback (most recent call last):
    ...
ValueError: Destination 0: weight must be positive, got -5

>>> weighted_transitions(s1, (s2, "ten"))
Traceback (most recent call last):
    ...
TypeError: Destination 0: weight must be a positive number, got str

```

## How it works

Under the hood, `weighted_transitions()`:

1. Creates a `_WeightedGroup` holding the weights and a `random.Random` instance.
2. Calls `source.to(target, **kwargs)` for each destination, creating standard
   transitions.
3. Attaches a lightweight condition callable to each transition's `cond` list.
4. When the event fires, the engine evaluates conditions in order. The first condition
   to run rolls the dice (using `random.choices`) and caches the result. Subsequent
   conditions check against the cache.
5. Only the selected transition's condition returns `True` — the engine picks it.

This means weighted transitions are fully compatible with all engine features:
{ref}`actions`, {ref}`validators-and-guards`, {ref}`listeners`, async engines,
and {ref}`diagram generation <diagram>`.
