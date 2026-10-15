from pathlib import Path

import pytest

CASES_DIR = Path(__file__).parent / "cases"

# Reason codes come from the UML/PSSM plan tracked in #692: `conflict:K<n>` (UML and the
# library disagree by design), `bug:B<n>` (library bug), `requires:<construct>` (no native
# spelling yet), `suite-defect:<OMG issue>`, `unclassified`. A reason lists every blocker.
# `lowered:<construct>` in LOWERED marks a pass that relies on the converter's lowering.
XFAIL_BOTH = {
    "Behavior_003-B": "requires:do_activity_accept: doActivity waits for an event",
    "Behavior_004": "requires:do_activity_accept: doActivity waits for an event",
    "Choice_005": "requires:choice, requires:junction: guards with side effects",
    "Deferred_001": "requires:defer: deferred event is not recalled",
    "Deferred_003": "requires:defer: deferred event is not recalled",
    "Deferred_004-A": "requires:defer: deferred event is not recalled",
    "Deferred_004-B": "requires:defer: deferred event is not recalled",
    "Deferred_005": "requires:defer: deferred event is not recalled",
    "Deferred_006-A": "requires:do_activity_accept, requires:defer: doActivity waits for an event",
    "Deferred_006-C": "requires:do_activity_accept, requires:defer: doActivity waits for an event",
    "Deferred_007": "requires:call_event, requires:defer: return value of a call",
    "Entering_004": "conflict:K13: region without initial gets a default entry",
    "Entering_009": "requires:entry_point: entry point effect runs after the state entry",
    "Entry_002-C": "requires:entry_point: entry point effect runs after the state entry",
    "Event_019-D": "requires:call_event: return value of a call",
    "Event_019-E": "requires:call_event: out parameters of a call",
    "Exit_001": "requires:exit_point: exit point effect runs before the state exit",
    "Exit_002": "requires:exit_point: exit points of orthogonal regions",
    "Exit_003": "requires:exit_point: exit point effect runs before the state exit",
    "Exiting_004": "requires:exit_point: exit point effect runs before the state exit",
    "Fork_002": "requires:fork: fork branch effects interleave with entries",
    "History_002-B": "unclassified: completions of two regions share one microstep",
    "History_002-D": "conflict:K10: history restores a final state, completion loops",
    "Join_001": "requires:join: join effects run after all exits",
    "Join_002": "requires:join: join effects run after all exits",
    "Join_003": "requires:join: join guard evaluated once per incoming transition",
    "Junction_002": "requires:junction: no branch enabled",
    "Junction_004": "requires:junction: initial junction picks a branch statically",
    "Junction_005": "requires:junction: effect and entry order",
    "TransitionExecutionAlgorithm": (
        "requires:exit_point, requires:entry_point: exit point effect order"
    ),
    "Standalone_002": (
        "requires:entry_point, requires:exit_point, requires:junction: entry point re-entry loops"
    ),
    "Standalone_003": "requires:call_event: out parameters of a call",
    "Terminate_001": "requires:terminate: terminate runs no exit behaviors",
    "Terminate_002": (
        "requires:terminate, requires:do_activity_accept: terminate runs no exit behaviors"
    ),
    "Transition_011-B": "requires:entry_point: entry point effect runs after the state entry",
    "Transition_011-C": "conflict:K13: container re-entered with default entry",
    "Transition_011-D": "requires:exit_point: exit point effect order",
    "Transition_011-E": (
        "requires:entry_point, requires:exit_point: entry and exit points on the same state"
    ),
    "Transition_017": (
        "conflict:K2, conflict:K14: composite completion does not wait for its doActivity, "
        "which never starts"
    ),
    "Transition_019": "requires:join: join effects run after all exits",
    "Transition_023": (
        "requires:junction, requires:entry_point, requires:exit_point: junction effect runs "
        "after the exits"
    ),
}
LOWERED = {
    "Behavior_003-A": "lowered:do_activity_accept: doActivity parked by the harness",
    "Choice_001": "lowered:choice: flattened into guarded transitions",
    "Choice_002": "lowered:choice: flattened into guarded transitions",
    "Choice_003": "lowered:choice: flattened into guarded transitions",
    "Choice_004": "lowered:choice: flattened into guarded transitions",
    "Deferred_002": "lowered:defer: the trace does not depend on the deferral",
    "Deferred_006-B": (
        "lowered:defer, lowered:do_activity_accept: the trace does not depend on the deferral"
    ),
    "Entry_002-A": "lowered:entry_point: flattened into transitions to the inner targets",
    "Entry_002-B": "lowered:entry_point: flattened into transitions to the inner targets",
    "Entry_002-D": "lowered:entry_point: flattened into transitions to the inner targets",
    "Entry_002-E": "lowered:entry_point: flattened into transitions to the inner targets",
    "Entry_002-F": "lowered:entry_point: flattened into transitions to the inner targets",
    "Exiting_002": "lowered:do_activity_accept: doActivity parked by the harness",
    "Fork_001": "lowered:fork, lowered:exit_point: one multi-target transition",
    "Junction_001": "lowered:junction: flattened into guarded transitions",
    "Junction_003": "lowered:junction: flattened into guarded transitions",
    "Junction_006": (
        "lowered:junction, lowered:entry_point, lowered:exit_point: "
        "flattened into guarded transitions"
    ),
    "Redefinition_001": "lowered:redefinition: merged into one machine by the converter",
    "Redefinition_002": "lowered:redefinition: merged into one machine by the converter",
    "Redefinition_003": "lowered:redefinition: merged into one machine by the converter",
    "Redefinition_004": "lowered:redefinition: merged into one machine by the converter",
    "Redefinition_005": "lowered:redefinition: merged into one machine by the converter",
    "Redefinition_006": (
        "lowered:redefinition, lowered:defer: merged into one machine by the converter"
    ),
    "Standalone_001": (
        "lowered:choice, lowered:entry_point, lowered:exit_point: "
        "flattened into guarded transitions"
    ),
    "Terminate_003": "lowered:terminate: mapped to a top-level final state",
}
"""Cases that pass only because the converter lowers a construct the library lacks.

They are not marked: they guard against regressions like any passing case, but they do not
show native support. When a construct gets a native spelling, the converter stops lowering
it and each of these cases is reclassified.
"""
XFAIL_SYNC_ONLY: dict[str, str] = {}
XFAIL_ASYNC_ONLY: dict[str, str] = {}

XFAIL_SYNC = {**XFAIL_BOTH, **XFAIL_SYNC_ONLY}
XFAIL_ASYNC = {**XFAIL_BOTH, **XFAIL_ASYNC_ONLY}


CASE_TIMEOUT_S = 30


def case_marks(case_id: str, is_async: bool) -> "list[pytest.MarkDecorator]":
    marks = [pytest.mark.timeout(CASE_TIMEOUT_S)]
    xfail = XFAIL_ASYNC if is_async else XFAIL_SYNC
    if case_id in xfail:
        marks.append(pytest.mark.xfail(reason=xfail[case_id]))
    return marks


def pytest_generate_tests(metafunc):
    if "pssm_case" not in metafunc.fixturenames:
        return
    is_async = "async" in metafunc.function.__name__
    metafunc.parametrize(
        "pssm_case",
        [
            pytest.param(path, id=path.stem, marks=case_marks(path.stem, is_async))
            for path in sorted(CASES_DIR.glob("*/*.yaml"))
        ],
    )
