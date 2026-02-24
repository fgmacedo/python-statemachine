"""Fellowship Quest: error.execution with conditions, listeners, and flow control.

Demonstrates how a single StateChart definition can produce different outcomes
depending on the character (listener) capabilities and the type of peril (exception).

Per SCXML spec:
- error.execution transitions follow the same rules as any other transition
- conditions are evaluated in document order; the first match wins
- the error object is available to conditions and handlers via the ``error`` kwarg
- executable content (``on`` callbacks) on error transitions is executed normally
- errors during error.execution processing are ignored to prevent infinite loops
"""

import pytest

from statemachine import State
from statemachine import StateChart

# ---------------------------------------------------------------------------
# Peril types (exception hierarchy)
# ---------------------------------------------------------------------------


class Peril(Exception):
    """Base class for all Middle-earth perils."""


class RingTemptation(Peril):
    """The One Ring tries to corrupt its bearer."""


class OrcAmbush(Peril):
    """An orc war party attacks the fellowship."""


class DarkSorcery(Peril):
    """Sauron's dark magic or a Nazgûl's sorcery."""


class TreacherousTerrain(Peril):
    """Natural hazards: avalanches, marshes, crumbling paths."""


class BalrogFury(Peril):
    """An ancient Balrog of Morgoth. Even wizards may fall."""


# ---------------------------------------------------------------------------
# Characters (listeners)
# ---------------------------------------------------------------------------


class Character:
    """Base class for fellowship members. Subclasses override capability flags.

    Condition methods are discovered by the StateChart via the listener mechanism,
    so the method names must match the ``cond`` strings on the error_execution
    transitions.
    """

    name: str = "Unknown"
    has_magic: bool = False
    has_ring_resistance: bool = False
    has_combat_prowess: bool = False
    has_endurance: bool = False

    def can_counter_with_magic(self, error=None, **kwargs):
        """Wizards can deflect dark sorcery — but not a Balrog."""
        return self.has_magic and isinstance(error, DarkSorcery)

    def can_resist_temptation(self, error=None, **kwargs):
        """Ring-bearers and the wise can resist the Ring's call."""
        return self.has_ring_resistance and isinstance(error, RingTemptation)

    def can_endure(self, error=None, **kwargs):
        """Warriors and the resilient survive physical perils."""
        return (self.has_combat_prowess and isinstance(error, OrcAmbush)) or (
            self.has_endurance and isinstance(error, TreacherousTerrain)
        )

    def __repr__(self):
        return self.name


class Gandalf(Character):
    name = "Gandalf"
    has_magic = True
    has_ring_resistance = True
    has_combat_prowess = True
    has_endurance = True


class Aragorn(Character):
    name = "Aragorn"
    has_combat_prowess = True
    has_endurance = True


class Frodo(Character):
    name = "Frodo"
    has_ring_resistance = True
    has_endurance = True  # mithril coat


class Legolas(Character):
    name = "Legolas"
    has_combat_prowess = True  # elven agility
    has_endurance = True


class Boromir(Character):
    name = "Boromir"
    has_combat_prowess = True
    has_endurance = True


class Pippin(Character):
    name = "Pippin"


class Samwise(Character):
    name = "Samwise"
    has_ring_resistance = True  # briefly bore the Ring without corruption
    has_endurance = True  # "I can't carry it for you, but I can carry you!"


# ---------------------------------------------------------------------------
# The StateChart
# ---------------------------------------------------------------------------


class FellowshipQuest(StateChart):
    """A quest through Middle-earth where perils are handled differently
    depending on the character's capabilities.

    Conditions on error_execution transitions (evaluated in document order):
    1. can_counter_with_magic — wizard deflects sorcery, stays adventuring
    2. can_resist_temptation  — ring resistance deflects corruption, stays adventuring
    3. can_endure             — physical resilience survives the blow, but wounded
    4. is_ring_corruption     — if the peril is ring corruption, route to corrupted
    5. (no condition)         — fallback: the character falls

    From wounded state, any further peril is fatal (no conditions).
    """

    adventuring = State("adventuring", initial=True)
    wounded = State("wounded")
    corrupted = State("corrupted", final=True)
    fallen = State("fallen", final=True)
    healed = State("healed", final=True)

    face_peril = adventuring.to(adventuring, on="encounter_danger")
    face_peril_wounded = wounded.to(wounded, on="encounter_danger")

    # error_execution transitions — document order determines priority.
    # Character capability conditions are resolved from the listener.
    error_execution = (
        adventuring.to(adventuring, cond="can_counter_with_magic")
        | adventuring.to(adventuring, cond="can_resist_temptation")
        | adventuring.to(wounded, cond="can_endure", on="take_hit")
        | adventuring.to(corrupted, cond="is_ring_corruption")
        | adventuring.to(fallen)
        | wounded.to(fallen)
    )

    recover = wounded.to(healed)

    wound_description: "str | None" = None

    def encounter_danger(self, peril, **kwargs):
        raise peril

    def is_ring_corruption(self, error=None, **kwargs):
        """Universal condition (on the SM itself, not character-dependent)."""
        return isinstance(error, RingTemptation)

    def take_hit(self, error=None, **kwargs):
        self.wound_description = str(error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# State name aliases for readable parametrize IDs
ADVENTURING = "adventuring"
WOUNDED = "wounded"
CORRUPTED = "corrupted"
FALLEN = "fallen"


def _state_by_name(sm, name):
    return getattr(sm, name)


# ---------------------------------------------------------------------------
# Tests — single-peril outcome matrix
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    ("character", "peril", "expected"),
    [
        # --- Gandalf: magic + ring resistance + combat + endurance ---
        pytest.param(
            Gandalf(), DarkSorcery("Nazgûl screams"), ADVENTURING, id="gandalf-deflects-sorcery"
        ),
        pytest.param(
            Gandalf(),
            RingTemptation("The Ring calls to power"),
            ADVENTURING,
            id="gandalf-resists-ring",
        ),
        pytest.param(Gandalf(), OrcAmbush("Goblins in Moria"), WOUNDED, id="gandalf-endures-orcs"),
        pytest.param(
            Gandalf(),
            TreacherousTerrain("Caradhras blizzard"),
            WOUNDED,
            id="gandalf-endures-terrain",
        ),
        pytest.param(Gandalf(), BalrogFury("Flame of Udûn"), FALLEN, id="gandalf-falls-to-balrog"),
        # --- Aragorn: combat + endurance ---
        pytest.param(
            Aragorn(),
            DarkSorcery("Mouth of Sauron's curse"),
            FALLEN,
            id="aragorn-falls-to-sorcery",
        ),
        pytest.param(
            Aragorn(),
            RingTemptation("The Ring offers kingship"),
            CORRUPTED,
            id="aragorn-corrupted-by-ring",
        ),
        pytest.param(Aragorn(), OrcAmbush("Uruk-hai charge"), WOUNDED, id="aragorn-endures-orcs"),
        pytest.param(
            Aragorn(),
            TreacherousTerrain("Caradhras avalanche"),
            WOUNDED,
            id="aragorn-endures-terrain",
        ),
        # --- Frodo: ring resistance + endurance (mithril) ---
        pytest.param(
            Frodo(), DarkSorcery("Witch-king's blade"), FALLEN, id="frodo-falls-to-sorcery"
        ),
        pytest.param(
            Frodo(), RingTemptation("The Ring whispers"), ADVENTURING, id="frodo-resists-ring"
        ),
        pytest.param(Frodo(), OrcAmbush("Cirith Ungol orcs"), FALLEN, id="frodo-falls-to-orcs"),
        pytest.param(
            Frodo(),
            TreacherousTerrain("Cave troll stab (mithril saves)"),
            WOUNDED,
            id="frodo-endures-terrain-mithril",
        ),
        # --- Legolas: combat + endurance ---
        pytest.param(Legolas(), DarkSorcery("Dark spell"), FALLEN, id="legolas-falls-to-sorcery"),
        pytest.param(
            Legolas(),
            RingTemptation("The Ring promises immortal forest"),
            CORRUPTED,
            id="legolas-corrupted-by-ring",
        ),
        pytest.param(Legolas(), OrcAmbush("Orc arrows rain"), WOUNDED, id="legolas-endures-orcs"),
        # --- Boromir: combat + endurance, no ring resistance ---
        pytest.param(
            Boromir(),
            RingTemptation("Give me the Ring!"),
            CORRUPTED,
            id="boromir-corrupted-by-ring",
        ),
        pytest.param(Boromir(), OrcAmbush("Lurtz attacks"), WOUNDED, id="boromir-endures-orcs"),
        # --- Samwise: ring resistance + endurance ---
        pytest.param(
            Samwise(),
            RingTemptation("Ring tempts with gardens"),
            ADVENTURING,
            id="samwise-resists-ring",
        ),
        pytest.param(
            Samwise(),
            TreacherousTerrain("Stairs of Cirith Ungol"),
            WOUNDED,
            id="samwise-endures-terrain",
        ),
        pytest.param(
            Samwise(), DarkSorcery("Shelob's darkness"), FALLEN, id="samwise-falls-to-sorcery"
        ),
        pytest.param(Samwise(), OrcAmbush("Orc patrol"), FALLEN, id="samwise-falls-to-orcs"),
        # --- Pippin: no special capabilities ---
        pytest.param(
            Pippin(),
            RingTemptation("The Ring shows second breakfast"),
            CORRUPTED,
            id="pippin-corrupted-by-ring",
        ),
        pytest.param(
            Pippin(), DarkSorcery("Palantír vision"), FALLEN, id="pippin-falls-to-sorcery"
        ),
        pytest.param(Pippin(), OrcAmbush("Troll swings"), FALLEN, id="pippin-falls-to-orcs"),
        pytest.param(
            Pippin(), TreacherousTerrain("Dead Marshes"), FALLEN, id="pippin-falls-to-terrain"
        ),
    ],
)
def test_single_peril_outcome(character, peril, expected):
    """Each character × peril combination produces the expected outcome."""
    sm = FellowshipQuest(listeners=[character])
    sm.send("face_peril", peril=peril)
    assert sm.configuration == {_state_by_name(sm, expected)}


# ---------------------------------------------------------------------------
# Tests — on callback receives error context
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    ("character", "peril", "expect_wound"),
    [
        pytest.param(
            Aragorn(), OrcAmbush("Poisoned orc blade"), "Poisoned orc blade", id="wound-from-orcs"
        ),
        pytest.param(
            Legolas(),
            TreacherousTerrain("Caradhras ice"),
            "Caradhras ice",
            id="wound-from-terrain",
        ),
        pytest.param(Gandalf(), DarkSorcery("Nazgûl"), None, id="no-wound-when-deflected"),
        pytest.param(
            Boromir(), RingTemptation("The Ring calls"), None, id="no-wound-when-corrupted"
        ),
    ],
)
def test_wound_description(character, peril, expect_wound):
    """The take_hit callback stores the wound description only when can_endure matches."""
    sm = FellowshipQuest(listeners=[character])
    sm.send("face_peril", peril=peril)
    assert sm.wound_description == expect_wound


# ---------------------------------------------------------------------------
# Tests — multi-peril sagas
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    ("character", "perils_and_states"),
    [
        pytest.param(
            Gandalf(),
            [
                (DarkSorcery("Saruman's blast"), ADVENTURING),
                (RingTemptation("The Ring calls"), ADVENTURING),
                (DarkSorcery("Witch-king's curse"), ADVENTURING),
                (OrcAmbush("Moria goblins"), WOUNDED),
            ],
            id="gandalf-saga-deflects-three-then-wounded",
        ),
        pytest.param(
            Frodo(),
            [
                (RingTemptation("Ring at Weathertop"), ADVENTURING),
                (RingTemptation("Ring at Amon Hen"), ADVENTURING),
                (TreacherousTerrain("Emyn Muil rocks"), WOUNDED),
            ],
            id="frodo-saga-resists-ring-twice-then-wounded",
        ),
        pytest.param(
            Samwise(),
            [
                (RingTemptation("Ring offers a garden"), ADVENTURING),
                (TreacherousTerrain("Stairs of Cirith Ungol"), WOUNDED),
            ],
            id="samwise-saga-resists-ring-then-wounded",
        ),
    ],
)
def test_multi_peril_saga(character, perils_and_states):
    """Characters face a sequence of perils — each step checked."""
    sm = FellowshipQuest(listeners=[character])
    for peril, expected in perils_and_states:
        sm.send("face_peril", peril=peril)
        assert sm.configuration == {_state_by_name(sm, expected)}


# ---------------------------------------------------------------------------
# Tests — wounded then second peril (always fatal)
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    ("character", "first_peril", "second_peril"),
    [
        pytest.param(
            Aragorn(),
            OrcAmbush("First wave"),
            OrcAmbush("Second wave"),
            id="aragorn-wounded-then-falls",
        ),
        pytest.param(
            Boromir(),
            OrcAmbush("Lurtz's arrows"),
            RingTemptation("The Ring in his final moments"),
            id="boromir-wounded-then-corrupted-by-ring-but-falls",
        ),
        pytest.param(
            Legolas(),
            TreacherousTerrain("Ice bridge cracks"),
            DarkSorcery("Shadow spell"),
            id="legolas-wounded-then-falls",
        ),
    ],
)
def test_wounded_then_second_peril_is_fatal(character, first_peril, second_peril):
    """A wounded character facing any second peril always falls —
    no conditions on the wounded→fallen transition."""
    sm = FellowshipQuest(listeners=[character])
    sm.send("face_peril", peril=first_peril)
    assert sm.configuration == {sm.wounded}

    sm.send("face_peril_wounded", peril=second_peril)
    assert sm.configuration == {sm.fallen}


# ---------------------------------------------------------------------------
# Tests — recovery after wound
# ---------------------------------------------------------------------------


@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    ("character", "peril"),
    [
        pytest.param(Aragorn(), TreacherousTerrain("Cliff fall"), id="aragorn-recovers"),
        pytest.param(Gandalf(), OrcAmbush("Goblin arrow"), id="gandalf-recovers"),
        pytest.param(Frodo(), TreacherousTerrain("Shelob's lair"), id="frodo-recovers"),
    ],
)
def test_recovery_after_wound(character, peril):
    """A wounded character can recover and reach a positive ending."""
    sm = FellowshipQuest(listeners=[character])
    sm.send("face_peril", peril=peril)
    assert sm.configuration == {sm.wounded}

    sm.send("recover")
    assert sm.configuration == {sm.healed}
