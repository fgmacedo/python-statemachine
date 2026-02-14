import pytest
from statemachine.exceptions import InvalidDefinition

from statemachine import Event
from statemachine import State
from statemachine import StateChart
from statemachine import StateMachine


class ErrorInGuardSC(StateChart):
    initial = State("initial", initial=True)
    error_state = State("error_state", final=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)
    error_execution = Event(initial.to(error_state), id="error.execution")

    def bad_guard(self):
        raise RuntimeError("guard failed")


class ErrorInOnEnterSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2)
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def on_enter_s2(self):
        raise RuntimeError("on_enter failed")


class ErrorInActionSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")


class ErrorInAfterSC(StateChart):
    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, after="bad_after")
    error_execution = Event(s2.to(error_state), id="error.execution")

    def bad_after(self):
        raise RuntimeError("after failed")


class ErrorInGuardSM(StateMachine):
    """StateMachine subclass: exceptions should propagate."""

    initial = State("initial", initial=True)

    go = initial.to(initial, cond="bad_guard") | initial.to(initial)

    def bad_guard(self):
        raise RuntimeError("guard failed")


class ErrorInActionSMWithFlag(StateMachine):
    """StateMachine subclass with error_on_execution = True."""

    error_on_execution = True

    s1 = State("s1", initial=True)
    s2 = State("s2")
    error_state = State("error_state", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(error_state) | s2.to(error_state), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")


class ErrorInErrorHandlerSC(StateChart):
    """Error in error.execution handler should not cause infinite loop."""

    s1 = State("s1", initial=True)
    s2 = State("s2", final=True)

    go = s1.to(s2, on="bad_action")
    error_execution = Event(s1.to(s1, on="bad_error_handler"), id="error.execution")

    def bad_action(self):
        raise RuntimeError("action failed")

    def bad_error_handler(self):
        raise RuntimeError("error handler also failed")


def test_exception_in_guard_sends_error_execution():
    """Exception in guard returns False and sends error.execution event."""
    sm = ErrorInGuardSC()
    assert sm.configuration == {sm.initial}

    sm.send("go")

    # The bad_guard raises, so error.execution is sent, transitioning to error_state
    assert sm.configuration == {sm.error_state}


def test_exception_in_on_enter_sends_error_execution():
    """Exception in on_enter sends error.execution and rolls back configuration."""
    sm = ErrorInOnEnterSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # on_enter_s2 raises, config is rolled back to s1, then error.execution fires
    assert sm.configuration == {sm.error_state}


def test_exception_in_action_sends_error_execution():
    """Exception in transition 'on' action sends error.execution."""
    sm = ErrorInActionSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # bad_action raises during transition, config rolls back to s1,
    # then error.execution fires
    assert sm.configuration == {sm.error_state}


def test_exception_in_after_sends_error_execution_no_rollback():
    """Exception in 'after' action sends error.execution but does NOT roll back."""
    sm = ErrorInAfterSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    # Transition s1->s2 completes, then bad_after raises,
    # error.execution fires from s2 -> error_state
    assert sm.configuration == {sm.error_state}


def test_statemachine_exception_propagates():
    """StateMachine (error_on_execution=False) should propagate exceptions normally."""
    sm = ErrorInGuardSM()
    assert sm.configuration == {sm.initial}

    # The bad_guard raises RuntimeError, which should propagate
    with pytest.raises(RuntimeError, match="guard failed"):
        sm.send("go")


def test_invalid_definition_always_propagates():
    """InvalidDefinition should always propagate regardless of error_on_execution."""

    class BadDefinitionSC(StateChart):
        s1 = State("s1", initial=True)
        s2 = State("s2", final=True)

        go = s1.to(s2, cond="bad_cond")

        def bad_cond(self):
            raise InvalidDefinition("bad definition")

    sm = BadDefinitionSC()
    with pytest.raises(InvalidDefinition, match="bad definition"):
        sm.send("go")


def test_error_in_error_handler_no_infinite_loop():
    """Error while processing error.execution should not cause infinite loop."""
    sm = ErrorInErrorHandlerSC()
    assert sm.configuration == {sm.s1}

    # bad_action raises -> error.execution fires -> bad_error_handler raises
    # Second error during error.execution processing is ignored (logged as warning)
    sm.send("go")

    # Machine should still be in s1 (rolled back from failed transition)
    assert sm.configuration == {sm.s1}


def test_statemachine_with_error_on_execution_true():
    """Custom StateMachine subclass with error_on_execution=True should catch errors."""
    sm = ErrorInActionSMWithFlag()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    assert sm.configuration == {sm.error_state}


def test_error_data_available_in_error_execution_handler():
    """The error object should be available in the error.execution event kwargs."""
    received_errors = []

    class ErrorDataSC(StateChart):
        s1 = State("s1", initial=True)
        error_state = State("error_state", final=True)

        go = s1.to(s1, on="bad_action")
        error_execution = Event(s1.to(error_state, on="handle_error"), id="error.execution")

        def bad_action(self):
            raise RuntimeError("specific error message")

        def handle_error(self, error=None, **kwargs):
            received_errors.append(error)

    sm = ErrorDataSC()
    sm.send("go")

    assert sm.configuration == {sm.error_state}
    assert len(received_errors) == 1
    assert isinstance(received_errors[0], RuntimeError)
    assert str(received_errors[0]) == "specific error message"


# --- Tests for error_ naming convention ---


class ErrorConventionTransitionListSC(StateChart):
    """Using bare TransitionList with error_ prefix auto-registers dot notation."""

    s1 = State("s1", initial=True)
    error_state = State("error_state", final=True)

    go = s1.to(s1, on="bad_action")
    error_execution = s1.to(error_state)

    def bad_action(self):
        raise RuntimeError("action failed")


class ErrorConventionEventSC(StateChart):
    """Using Event without explicit id with error_ prefix auto-registers dot notation."""

    s1 = State("s1", initial=True)
    error_state = State("error_state", final=True)

    go = s1.to(s1, on="bad_action")
    error_execution = Event(s1.to(error_state))

    def bad_action(self):
        raise RuntimeError("action failed")


def test_error_convention_with_transition_list():
    """Bare TransitionList with error_ prefix matches error.execution event."""
    sm = ErrorConventionTransitionListSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    assert sm.configuration == {sm.error_state}


def test_error_convention_with_event_no_explicit_id():
    """Event without explicit id with error_ prefix matches error.execution event."""
    sm = ErrorConventionEventSC()
    assert sm.configuration == {sm.s1}

    sm.send("go")

    assert sm.configuration == {sm.error_state}


def test_error_convention_preserves_explicit_id():
    """Event with explicit id= should NOT be modified by naming convention."""

    class ExplicitIdSC(StateChart):
        s1 = State("s1", initial=True)
        error_state = State("error_state", final=True)

        go = s1.to(s1, on="bad_action")
        error_execution = Event(s1.to(error_state), id="error.execution")

        def bad_action(self):
            raise RuntimeError("action failed")

    sm = ExplicitIdSC()
    sm.send("go")
    assert sm.configuration == {sm.error_state}


def test_non_error_prefix_unchanged():
    """Attributes NOT starting with error_ should not get dot-notation alias."""

    class NormalSC(StateChart):
        s1 = State("s1", initial=True)
        s2 = State("s2", final=True)

        go = s1.to(s2)

    sm = NormalSC()
    # The 'go' event should only match 'go', not 'g.o'
    sm.send("go")
    assert sm.configuration == {sm.s2}


# --- LOTR-themed error_ convention and error handling edge cases ---


@pytest.mark.timeout(5)
class TestErrorConventionLOTR:
    """Error handling and error_ naming convention using Lord of the Rings theme."""

    def test_ring_corrupts_bearer_convention_transition_list(self):
        """Frodo puts on the Ring (action fails) -> error.execution via bare TransitionList."""

        class FrodoJourney(StateChart):
            the_shire = State("the_shire", initial=True)
            corrupted = State("corrupted", final=True)

            put_on_ring = the_shire.to(the_shire, on="bear_the_ring")
            error_execution = the_shire.to(corrupted)

            def bear_the_ring(self):
                raise RuntimeError("The Ring's corruption is too strong")

        sm = FrodoJourney()
        assert sm.configuration == {sm.the_shire}
        sm.send("put_on_ring")
        assert sm.configuration == {sm.corrupted}

    def test_ring_corrupts_bearer_convention_event(self):
        """Same as above but using Event() without explicit id."""

        class FrodoJourney(StateChart):
            the_shire = State("the_shire", initial=True)
            corrupted = State("corrupted", final=True)

            put_on_ring = the_shire.to(the_shire, on="bear_the_ring")
            error_execution = Event(the_shire.to(corrupted))

            def bear_the_ring(self):
                raise RuntimeError("The Ring's corruption is too strong")

        sm = FrodoJourney()
        sm.send("put_on_ring")
        assert sm.configuration == {sm.corrupted}

    def test_explicit_id_takes_precedence(self):
        """Explicit id='error.execution' is preserved, convention does not interfere."""

        class GandalfBattle(StateChart):
            bridge = State("bridge", initial=True)
            fallen = State("fallen", final=True)

            fight_balrog = bridge.to(bridge, on="you_shall_not_pass")
            error_execution = Event(bridge.to(fallen), id="error.execution")

            def you_shall_not_pass(self):
                raise RuntimeError("Balrog breaks the bridge")

        sm = GandalfBattle()
        sm.send("fight_balrog")
        assert sm.configuration == {sm.fallen}

    def test_error_data_passed_to_handler(self):
        """The original error is available in the error handler kwargs."""
        captured = []

        class PalantirVision(StateChart):
            seeing = State("seeing", initial=True)
            madness = State("madness", final=True)

            gaze = seeing.to(seeing, on="look_into_palantir")
            error_execution = seeing.to(madness, on="saurons_influence")

            def look_into_palantir(self):
                raise RuntimeError("Sauron's eye burns")

            def saurons_influence(self, error=None, **kwargs):
                captured.append(error)

        sm = PalantirVision()
        sm.send("gaze")
        assert sm.configuration == {sm.madness}
        assert len(captured) == 1
        assert str(captured[0]) == "Sauron's eye burns"

    def test_error_in_guard_with_convention(self):
        """Error in a guard condition triggers error.execution via convention."""

        class GateOfMoria(StateChart):
            outside = State("outside", initial=True)
            trapped = State("trapped", final=True)

            speak_friend = outside.to(outside, cond="know_password") | outside.to(outside)
            error_execution = outside.to(trapped)

            def know_password(self):
                raise RuntimeError("The Watcher attacks")

        sm = GateOfMoria()
        sm.send("speak_friend")
        assert sm.configuration == {sm.trapped}

    def test_error_in_on_enter_with_convention(self):
        """Error in on_enter triggers error.execution via convention."""

        class EnterMordor(StateChart):
            ithilien = State("ithilien", initial=True)
            mordor = State("mordor")
            captured = State("captured", final=True)

            march = ithilien.to(mordor)
            error_execution = ithilien.to(captured) | mordor.to(captured)

            def on_enter_mordor(self):
                raise RuntimeError("One does not simply walk into Mordor")

        sm = EnterMordor()
        sm.send("march")
        assert sm.configuration == {sm.captured}

    def test_error_in_after_with_convention(self):
        """Error in 'after' callback: transition completes, then error.execution fires."""

        class HelmDeep(StateChart):
            defending = State("defending", initial=True)
            breached = State("breached")
            fallen = State("fallen", final=True)

            charge = defending.to(breached, after="wall_explodes")
            error_execution = breached.to(fallen)

            def wall_explodes(self):
                raise RuntimeError("Uruk-hai detonated the wall")

        sm = HelmDeep()
        sm.send("charge")
        # 'after' runs after the transition completes (defending->breached),
        # so error.execution fires from breached->fallen
        assert sm.configuration == {sm.fallen}

    def test_error_in_error_handler_no_loop_with_convention(self):
        """Error in error handler must NOT loop infinitely, even with convention."""

        class OneRingTemptation(StateChart):
            carrying = State("carrying", initial=True)
            resisting = State("resisting", final=True)

            tempt = carrying.to(carrying, on="resist")
            error_execution = carrying.to(carrying, on="struggle")
            throw_ring = carrying.to(resisting)

            def resist(self):
                raise RuntimeError("The Ring whispers")

            def struggle(self):
                raise RuntimeError("Cannot resist the Ring")

        sm = OneRingTemptation()
        sm.send("tempt")
        # Error in error handler is ignored, machine stays in carrying
        assert sm.configuration == {sm.carrying}

    def test_multiple_source_states_with_convention(self):
        """error_execution from multiple states using | operator."""

        class FellowshipPath(StateChart):
            rivendell = State("rivendell", initial=True)
            moria = State("moria")
            doom = State("doom", final=True)

            travel = rivendell.to(moria, on="enter_mines")
            error_execution = rivendell.to(doom) | moria.to(doom)

            def enter_mines(self):
                raise RuntimeError("The Balrog awakens")

        sm = FellowshipPath()
        sm.send("travel")
        assert sm.configuration == {sm.doom}

    def test_convention_with_self_transition_to_final(self):
        """Self-transition error leading to a different state via error handler."""

        class GollumDilemma(StateChart):
            following = State("following", initial=True)
            betrayed = State("betrayed", final=True)

            precious = following.to(following, on="obsess")
            error_execution = following.to(betrayed)

            def obsess(self):
                raise RuntimeError("My precious!")

        sm = GollumDilemma()
        sm.send("precious")
        assert sm.configuration == {sm.betrayed}

    def test_statemachine_with_convention_and_flag(self):
        """StateMachine with error_on_execution=True uses the error_ convention."""

        class SarumanBetrayal(StateMachine):
            error_on_execution = True

            white_council = State("white_council", initial=True)
            orthanc = State("orthanc", final=True)

            reveal = white_council.to(white_council, on="betray")
            error_execution = white_council.to(orthanc)

            def betray(self):
                raise RuntimeError("Saruman turns to Sauron")

        sm = SarumanBetrayal()
        sm.send("reveal")
        assert sm.configuration == {sm.orthanc}

    def test_statemachine_without_flag_propagates(self):
        """StateMachine without error_on_execution=True propagates errors even with convention."""

        class AragornSword(StateMachine):
            broken = State("broken", initial=True)

            reforge = broken.to(broken, on="attempt_reforge")
            error_execution = broken.to(broken)

            def attempt_reforge(self):
                raise RuntimeError("Narsil cannot be reforged yet")

        sm = AragornSword()
        with pytest.raises(RuntimeError, match="Narsil cannot be reforged yet"):
            sm.send("reforge")

    def test_no_error_handler_defined(self):
        """error.execution fires but no matching transition -> silently ignored (StateChart)."""

        class Treebeard(StateChart):
            ent_moot = State("ent_moot", initial=True)

            deliberate = ent_moot.to(ent_moot, on="hasty_decision")

            def hasty_decision(self):
                raise RuntimeError("Don't be hasty!")

        sm = Treebeard()
        sm.send("deliberate")
        # No error_execution handler, so error.execution is ignored
        # (allow_event_without_transition=True on StateChart)
        assert sm.configuration == {sm.ent_moot}

    def test_recovery_from_error_allows_further_transitions(self):
        """After handling error.execution, the machine can continue processing events."""

        class FrodoQuest(StateChart):
            shire = State("shire", initial=True)
            journey = State("journey")
            mount_doom = State("mount_doom", final=True)

            depart = shire.to(shire, on="pack_bags")
            error_execution = shire.to(journey)
            continue_quest = journey.to(mount_doom)

            def pack_bags(self):
                raise RuntimeError("Nazgul attack!")

        sm = FrodoQuest()
        sm.send("depart")
        assert sm.configuration == {sm.journey}

        # Machine is still alive, can process more events
        sm.send("continue_quest")
        assert sm.configuration == {sm.mount_doom}

    def test_error_nested_dots_convention(self):
        """error_communication_failed -> also matches error.communication.failed."""

        class BeaconOfGondor(StateChart):
            waiting = State("waiting", initial=True)
            lit = State("lit")
            failed = State("failed", final=True)

            light_beacon = waiting.to(lit, on="kindle")
            error_communication_failed = lit.to(failed)

            def kindle(self):
                raise RuntimeError("The beacon wood is wet")

        sm = BeaconOfGondor()
        sm.send("light_beacon")
        # error.communication.failed won't match error.execution, but
        # error_communication_failed will match "error_communication_failed"
        # The engine sends "error.execution" which does NOT match
        # "error_communication_failed" or "error.communication.failed".
        # So the error is unhandled and silently ignored (StateChart default).
        assert sm.configuration == {sm.waiting}

    def test_multiple_errors_sequential(self):
        """Multiple events that fail are each handled by error.execution."""
        error_count = []

        class BoromirLastStand(StateChart):
            fighting = State("fighting", initial=True)
            wounded = State("wounded")
            fallen = State("fallen", final=True)

            strike = fighting.to(fighting, on="swing_sword")
            error_execution = fighting.to(wounded, on="take_arrow") | wounded.to(
                fallen, on="take_arrow"
            )
            retreat = wounded.to(wounded)

            def swing_sword(self):
                raise RuntimeError("Arrow from Lurtz")

            def take_arrow(self, **kwargs):
                error_count.append(1)

        sm = BoromirLastStand()
        sm.send("strike")
        assert sm.configuration == {sm.wounded}
        assert len(error_count) == 1

        # Second error from wounded state leads to fallen
        sm.send("retreat")  # no error, just moves wounded->wounded
        assert sm.configuration == {sm.wounded}

    def test_invalid_definition_propagates_despite_convention(self):
        """InvalidDefinition always propagates even with error_ convention."""

        class CursedRing(StateChart):
            wearing = State("wearing", initial=True)
            corrupted = State("corrupted", final=True)

            use_ring = wearing.to(wearing, cond="ring_check")
            error_execution = wearing.to(corrupted)

            def ring_check(self):
                raise InvalidDefinition("Ring of Power has no valid definition")

        sm = CursedRing()
        with pytest.raises(InvalidDefinition, match="Ring of Power"):
            sm.send("use_ring")


@pytest.mark.timeout(5)
class TestErrorHandlerBehaviorLOTR:
    """Advanced error handler behavior: on callbacks, conditions, flow control,
    and error-in-handler scenarios. SCXML spec compliance.

    All using Lord of the Rings theme.
    """

    def test_on_callback_executes_on_error_transition(self):
        """An `on` callback on the error_execution transition is executed."""
        actions_log = []

        class MirrorOfGaladriel(StateChart):
            gazing = State("gazing", initial=True)
            shattered = State("shattered", final=True)

            look = gazing.to(gazing, on="peer_into_mirror")
            error_execution = gazing.to(shattered, on="vision_of_doom")

            def peer_into_mirror(self):
                raise RuntimeError("Visions of Sauron")

            def vision_of_doom(self, **kwargs):
                actions_log.append("vision_of_doom executed")

        sm = MirrorOfGaladriel()
        sm.send("look")
        assert sm.configuration == {sm.shattered}
        assert actions_log == ["vision_of_doom executed"]

    def test_on_callback_receives_error_kwarg(self):
        """The `on` callback receives the original error via `error` kwarg."""
        captured = {}

        class DeadMarshes(StateChart):
            walking = State("walking", initial=True)
            lost = State("lost", final=True)

            follow_gollum = walking.to(walking, on="step_wrong")
            error_execution = walking.to(lost, on="fall_in_marsh")

            def step_wrong(self):
                raise RuntimeError("The dead faces call")

            def fall_in_marsh(self, error=None, **kwargs):
                captured["error"] = error
                captured["type"] = type(error).__name__

        sm = DeadMarshes()
        sm.send("follow_gollum")
        assert sm.configuration == {sm.lost}
        assert captured["type"] == "RuntimeError"
        assert str(captured["error"]) == "The dead faces call"

    def test_error_in_on_callback_of_error_handler_is_ignored(self):
        """If the `on` callback of error.execution raises, the second error is ignored.

        Per SCXML spec: errors during error.execution processing must not recurse.
        The machine should roll back to the configuration before the failed error handler.
        """

        class MountDoom(StateChart):
            climbing = State("climbing", initial=True)
            fallen_into_lava = State("fallen_into_lava", final=True)

            ascend = climbing.to(climbing, on="slip")
            error_execution = climbing.to(fallen_into_lava, on="gollum_intervenes")
            survive = climbing.to(fallen_into_lava)  # reachability

            def slip(self):
                raise RuntimeError("Rocks crumble")

            def gollum_intervenes(self):
                raise RuntimeError("Gollum bites the finger!")

        sm = MountDoom()
        sm.send("ascend")
        # Error in error handler is ignored, config rolled back to climbing
        assert sm.configuration == {sm.climbing}

    def test_condition_on_error_transition_routes_to_different_states(self):
        """Two error_execution transitions with different cond guards route errors
        to different target states based on runtime conditions."""

        class BattleOfPelennor(StateChart):
            fighting = State("fighting", initial=True)
            retreating = State("retreating")
            fallen = State("fallen", final=True)

            charge = fighting.to(fighting, on="attack")
            error_execution = fighting.to(retreating, cond="is_recoverable") | fighting.to(fallen)
            regroup = retreating.to(fighting)

            is_minor_wound = False

            def attack(self):
                raise RuntimeError("Oliphant charges!")

            def is_recoverable(self, error=None, **kwargs):
                return self.is_minor_wound

        # Serious wound -> falls
        sm = BattleOfPelennor()
        sm.is_minor_wound = False
        sm.send("charge")
        assert sm.configuration == {sm.fallen}

        # Minor wound -> retreats
        sm2 = BattleOfPelennor()
        sm2.is_minor_wound = True
        sm2.send("charge")
        assert sm2.configuration == {sm2.retreating}

    def test_condition_inspects_error_type_to_route(self):
        """Conditions can inspect the error type to decide the error transition."""

        class PathsOfTheDead(StateChart):
            entering = State("entering", initial=True)
            cursed = State("cursed")
            fled = State("fled", final=True)
            conquered = State("conquered", final=True)

            venture = entering.to(entering, on="face_the_dead")
            error_execution = entering.to(cursed, cond="is_fear") | entering.to(conquered)
            escape = cursed.to(fled)

            def face_the_dead(self):
                raise ValueError("The ghosts overwhelm with fear")

            def is_fear(self, error=None, **kwargs):
                return isinstance(error, ValueError)

        sm = PathsOfTheDead()
        sm.send("venture")
        assert sm.configuration == {sm.cursed}

    def test_condition_inspects_error_message_to_route(self):
        """Conditions can inspect the error message string."""

        class WeathertopAmbush(StateChart):
            camping = State("camping", initial=True)
            wounded = State("wounded")
            safe = State("safe", final=True)

            rest = camping.to(camping, on="keep_watch")
            error_execution = camping.to(wounded, cond="is_morgul_blade") | camping.to(safe)
            heal = wounded.to(safe)

            def keep_watch(self):
                raise RuntimeError("Morgul blade strikes Frodo")

            def is_morgul_blade(self, error=None, **kwargs):
                return error is not None and "Morgul" in str(error)

        sm = WeathertopAmbush()
        sm.send("rest")
        assert sm.configuration == {sm.wounded}

    def test_error_handler_can_set_machine_attributes(self):
        """The `on` handler on error.execution can modify the state machine instance,
        effectively controlling flow for subsequent transitions."""
        log = []

        class IsengardSiege(StateChart):
            besieging = State("besieging", initial=True)
            flooding = State("flooding")
            victory = State("victory", final=True)

            attack = besieging.to(besieging, on="ram_gates")
            error_execution = besieging.to(flooding, on="release_river")
            finish = flooding.to(victory)

            def ram_gates(self):
                raise RuntimeError("Gates too strong")

            def release_river(self, error=None, **kwargs):
                log.append(f"Ents release the river after: {error}")
                self.battle_outcome = "flooded"

        sm = IsengardSiege()
        sm.send("attack")
        assert sm.configuration == {sm.flooding}
        assert sm.battle_outcome == "flooded"
        assert len(log) == 1

        sm.send("finish")
        assert sm.configuration == {sm.victory}

    def test_error_recovery_then_second_error_handled(self):
        """After recovering from an error, a second error is also handled correctly."""
        errors_seen = []

        class MinasTirithDefense(StateChart):
            outer_wall = State("outer_wall", initial=True)
            inner_wall = State("inner_wall")
            citadel = State("citadel", final=True)

            defend_outer = outer_wall.to(outer_wall, on="hold_wall")
            error_execution = outer_wall.to(inner_wall, on="log_error") | inner_wall.to(
                citadel, on="log_error"
            )
            defend_inner = inner_wall.to(inner_wall, on="hold_wall")

            def hold_wall(self):
                raise RuntimeError("Wall breached!")

            def log_error(self, error=None, **kwargs):
                errors_seen.append(str(error))

        sm = MinasTirithDefense()

        # First error: outer_wall -> inner_wall
        sm.send("defend_outer")
        assert sm.configuration == {sm.inner_wall}
        assert errors_seen == ["Wall breached!"]

        # Second error: inner_wall -> citadel
        sm.send("defend_inner")
        assert sm.configuration == {sm.citadel}
        assert errors_seen == ["Wall breached!", "Wall breached!"]

    def test_all_conditions_false_error_unhandled(self):
        """If all error_execution conditions are False, error.execution is silently ignored."""

        class Shelob(StateChart):
            tunnel = State("tunnel", initial=True)

            sneak = tunnel.to(tunnel, on="enter_lair")
            error_execution = tunnel.to(tunnel, cond="never_true")

            def enter_lair(self):
                raise RuntimeError("Shelob attacks!")

            def never_true(self, **kwargs):
                return False

        sm = Shelob()
        sm.send("sneak")
        # No condition matched, error.execution ignored, stays in tunnel
        assert sm.configuration == {sm.tunnel}

    def test_error_in_before_callback_with_convention(self):
        """Error in a `before` callback is also caught and triggers error.execution."""

        class RivendellCouncil(StateChart):
            debating = State("debating", initial=True)
            disbanded = State("disbanded", final=True)

            propose = debating.to(debating, before="check_ring")
            error_execution = debating.to(disbanded)

            def check_ring(self):
                raise RuntimeError("Gimli tries to destroy the Ring")

        sm = RivendellCouncil()
        sm.send("propose")
        assert sm.configuration == {sm.disbanded}

    def test_error_in_exit_callback_with_convention(self):
        """Error in on_exit is caught per-block and triggers error.execution."""

        class LothlorienDeparture(StateChart):
            resting = State("resting", initial=True)
            river = State("river")
            lost = State("lost", final=True)

            depart = resting.to(river)
            error_execution = resting.to(lost) | river.to(lost)

            def on_exit_resting(self):
                raise RuntimeError("Galadriel's gifts cause delay")

        sm = LothlorienDeparture()
        sm.send("depart")
        assert sm.configuration == {sm.lost}


@pytest.mark.timeout(5)
class TestEngineErrorPropagation:
    def test_invalid_definition_in_enter_propagates(self):
        """InvalidDefinition during enter_states propagates and restores configuration."""

        class SM(StateChart):
            s1 = State(initial=True)
            s2 = State()

            go = s1.to(s2)

            def on_enter_s2(self, **kwargs):
                raise InvalidDefinition("Bad definition")

        sm = SM()
        with pytest.raises(InvalidDefinition, match="Bad definition"):
            sm.send("go")

    def test_invalid_definition_in_after_propagates(self):
        """InvalidDefinition in after callback propagates."""

        class SM(StateChart):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

            def after_go(self, **kwargs):
                raise InvalidDefinition("Bad after")

        sm = SM()
        with pytest.raises(InvalidDefinition, match="Bad after"):
            sm.send("go")

    def test_runtime_error_in_after_without_error_on_execution_propagates(self):
        """RuntimeError in after callback without error_on_execution raises."""

        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State(final=True)

            go = s1.to(s2)

            def after_go(self, **kwargs):
                raise RuntimeError("After boom")

        sm = SM()
        with pytest.raises(RuntimeError, match="After boom"):
            sm.send("go")

    def test_runtime_error_in_after_with_error_on_execution_handled(self):
        """RuntimeError in after callback with error_on_execution is caught."""

        class SM(StateChart):
            s1 = State(initial=True)
            s2 = State()
            error_state = State(final=True)

            go = s1.to(s2)
            error_execution = s2.to(error_state)

            def after_go(self, **kwargs):
                raise RuntimeError("After boom")

        sm = SM()
        sm.send("go")
        assert sm.configuration == {sm.error_state}

    def test_runtime_error_in_microstep_without_error_on_execution(self):
        """RuntimeError in microstep without error_on_execution raises."""

        class SM(StateMachine):
            s1 = State(initial=True)
            s2 = State()

            go = s1.to(s2)

            def on_enter_s2(self, **kwargs):
                raise RuntimeError("Microstep boom")

        sm = SM()
        with pytest.raises(RuntimeError, match="Microstep boom"):
            sm.send("go")


@pytest.mark.timeout(5)
def test_internal_queue_processes_raised_events():
    """Internal events raised during processing are handled."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State()
        s3 = State(final=True)

        go = s1.to(s2)
        next_step = s2.to(s3)

        def on_enter_s2(self, **kwargs):
            self.raise_("next_step")

    sm = SM()
    sm.send("go")
    assert sm.s3.is_active


@pytest.mark.timeout(5)
def test_engine_start_when_already_started():
    """start() is a no-op when state machine is already initialized."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State(final=True)

        go = s1.to(s2)

    sm = SM()
    sm._engine.start()
    assert sm.s1.is_active


@pytest.mark.timeout(5)
def test_error_in_internal_event_transition_caught_by_microstep():
    """Error in a transition triggered by an internal event is caught by _run_microstep."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()
        s3 = State()
        error_state = State(final=True)

        go = s1.to(s2)
        step = s2.to(s3, on="bad_action")
        error_execution = s2.to(error_state) | s3.to(error_state)

        def on_enter_s2(self, **kwargs):
            self.raise_("step")

        def bad_action(self):
            raise RuntimeError("Internal event error")

    sm = SM()
    sm.send("go")
    assert sm.configuration == {sm.error_state}


@pytest.mark.timeout(5)
def test_invalid_definition_in_internal_event_propagates():
    """InvalidDefinition in an internal event transition propagates through _run_microstep."""

    class SM(StateChart):
        s1 = State(initial=True)
        s2 = State()
        s3 = State()
        error_state = State(final=True)

        go = s1.to(s2)
        step = s2.to(s3, on="bad_action")
        error_execution = s2.to(error_state)

        def on_enter_s2(self, **kwargs):
            self.raise_("step")

        def bad_action(self):
            raise InvalidDefinition("Internal event bad definition")

    sm = SM()
    with pytest.raises(InvalidDefinition, match="Internal event bad definition"):
        sm.send("go")


@pytest.mark.timeout(5)
def test_runtime_error_in_internal_event_propagates_without_error_on_execution():
    """RuntimeError in internal event propagates when error_on_execution is False."""

    class SM(StateMachine):
        s1 = State(initial=True)
        s2 = State()
        s3 = State()

        go = s1.to(s2)
        step = s2.to(s3, on="bad_action")

        def on_enter_s2(self, **kwargs):
            self.raise_("step")

        def bad_action(self):
            raise RuntimeError("Internal event boom")

    sm = SM()
    with pytest.raises(RuntimeError, match="Internal event boom"):
        sm.send("go")
