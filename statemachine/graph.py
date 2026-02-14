from collections import deque
from typing import TYPE_CHECKING
from typing import Iterable
from typing import MutableSet

if TYPE_CHECKING:
    from .state import State


def visit_connected_states(state: "State"):
    visit = deque["State"]()
    already_visited = set()
    visit.append(state)
    while visit:
        state = visit.popleft()
        if state in already_visited:
            continue
        already_visited.add(state)
        yield state
        visit.extend(t.target for t in state.transitions if t.target)


def disconnected_states(starting_state: "State", all_states: MutableSet["State"]):
    visitable_states = set(visit_connected_states(starting_state))
    return all_states - visitable_states


def iterate_states_and_transitions(states: Iterable["State"]):
    for state in states:
        yield state
        yield from state.transitions
        if state.states:
            yield from iterate_states_and_transitions(state.states)
        if state.history:
            yield from iterate_states_and_transitions(state.history)


def iterate_states(states: Iterable["State"]):
    for state in states:
        yield state
        if state.states:
            yield from iterate_states(state.states)
        if state.history:
            yield from iterate_states(state.history)


def states_without_path_to_final_states(states: Iterable["State"]):
    return (
        state
        for state in states
        if not state.final and not any(s.final for s in visit_connected_states(state))
    )
