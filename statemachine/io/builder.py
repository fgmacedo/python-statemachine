"""Compile the neutral IR into StateChart class keyword arguments.

:class:`DefinitionBuilder` translates a :class:`~statemachine.io.model.StateMachineDefinition`
into the ``kwargs`` accepted by :func:`~statemachine.io.create_machine_class_from_definition`,
compiling guards and executable content through an
:class:`~statemachine.io.evaluators.Evaluator` (secure by default).

It is format-neutral and runtime-agnostic: anything that is a runtime concern
(system-variable injection, the invoke bootstrap, building invokers) is requested from a
:class:`RuntimeHooks` collaborator, so the builder never imports the concrete runtime and
there is no import cycle.
"""

from typing import Protocol

from .actions import Cond
from .actions import DoneDataCallable
from .actions import ExecuteBlock
from .actions import create_datamodel_action_callable
from .class_factory import HistoryDefinition
from .class_factory import StateDefinition
from .class_factory import TransitionDict
from .class_factory import TransitionsList
from .evaluators import Evaluator
from .model import HistoryState
from .model import InvokeDefinition
from .model import State
from .model import StateMachineDefinition
from .model import Transition


class RuntimeHooks(Protocol):
    """Runtime concerns the builder delegates back to the interpreter."""

    def initial_enter_prefix(
        self, is_invoked: bool
    ) -> list:  # pragma: no cover - structural Protocol
        """Callbacks to insert at the front of the initial state's ``enter`` list."""
        ...

    def definition_kwargs(self, definition) -> dict:  # pragma: no cover - structural Protocol
        """Extra kwargs for ``create_machine_class_from_definition`` (e.g. ``prepare_event``)."""
        ...

    def make_invoker(self, invoke_def: InvokeDefinition):  # pragma: no cover - structural Protocol
        """Build the invoke handler for an ``<invoke>`` definition."""
        ...


class DefinitionBuilder:
    """Translates the neutral IR into ``create_machine_class_from_definition`` kwargs."""

    def __init__(self, *, evaluator: Evaluator, hooks: RuntimeHooks):
        self._evaluator = evaluator
        self._hooks = hooks

    def build_class_kwargs(self, definition: StateMachineDefinition, *, is_invoked: bool) -> dict:
        states_dict = self._process_states(definition.states)

        # Find the initial state for inserting init callbacks
        try:
            initial_state = next(s for s in iter(states_dict.values()) if s.get("initial"))
        except StopIteration:
            initial_state = next(iter(states_dict.values()))

        if "enter" not in initial_state:
            initial_state["enter"] = []

        insert_pos = 0
        # Runtime callbacks that must run before the datamodel (e.g. invoke init).
        for callback in self._hooks.initial_enter_prefix(is_invoked):
            initial_state["enter"].insert(insert_pos, callback)  # type: ignore[union-attr]
            insert_pos += 1

        # Process datamodel (initial variables)
        if definition.datamodel:
            datamodel = create_datamodel_action_callable(definition.datamodel, self._evaluator)
            if datamodel:  # pragma: no branch – parse guarantees non-empty
                if isinstance(  # pragma: no branch – always a list from lines above
                    initial_state["enter"], list
                ):
                    initial_state["enter"].insert(insert_pos, datamodel)  # type: ignore[arg-type]

        return {"states": states_dict, **self._hooks.definition_kwargs(definition)}

    def _process_history(self, history: dict[str, HistoryState]) -> dict[str, HistoryDefinition]:
        states_dict: dict[str, HistoryDefinition] = {}
        for state_id, state in history.items():
            state_dict = HistoryDefinition()
            state_dict["type"] = state.type
            if state.transitions:
                state_dict["transitions"] = self._process_transitions(state.transitions)
            states_dict[state_id] = state_dict
        return states_dict

    def _process_states(self, states: dict[str, State]) -> dict[str, StateDefinition]:
        return {state_id: self._process_state(state) for state_id, state in states.items()}

    def _process_state(self, state: State) -> StateDefinition:  # noqa: C901
        state_dict = StateDefinition()
        if state.initial:
            state_dict["initial"] = True
        if state.final:
            state_dict["final"] = True
        if state.parallel:
            state_dict["parallel"] = True

        # Process enter actions (executable content first, then callback refs)
        enter_callables: list = [
            ExecuteBlock(content, self._evaluator)
            for content in state.onentry
            if not content.is_empty
        ]
        enter_callables.extend(state.enter_refs)
        if enter_callables:
            state_dict["enter"] = enter_callables
        if state.final and state.donedata:
            state_dict["donedata"] = DoneDataCallable(state.donedata, self._evaluator)

        # Process exit actions (executable content first, then callback refs)
        exit_callables: list = [
            ExecuteBlock(content, self._evaluator)
            for content in state.onexit
            if not content.is_empty
        ]
        exit_callables.extend(state.exit_refs)
        if exit_callables:
            state_dict["exit"] = exit_callables

        # Process transitions
        if state.transitions:
            state_dict["transitions"] = self._process_transitions(state.transitions)

        # Process invoke elements (delegated to the runtime)
        if state.invocations:
            invokers = [self._hooks.make_invoker(inv) for inv in state.invocations]
            state_dict["invoke"] = invokers  # type: ignore[typeddict-unknown-key]

        if state.states:
            state_dict["states"] = self._process_states(state.states)

        if state.history:
            state_dict["history"] = self._process_history(state.history)

        return state_dict

    def _process_transitions(self, transitions: list[Transition]):
        result: TransitionsList = []
        for transition in transitions:
            event = transition.event or None
            transition_dict: TransitionDict = {
                "event": event,
                "target": transition.target,
                "internal": transition.internal,
                "initial": transition.initial,
            }

            # Process guards (cond / unless) as compiled expressions
            if transition.cond:
                transition_dict["cond"] = self._compile_guard(transition.cond)
            if transition.unless:
                transition_dict["unless"] = self._compile_guard(transition.unless)

            # Each callback slot is executable content (compiled first) followed by the
            # callback references. `on` mirrors SCXML; `before`/`after` are native-only
            # library lifecycle slots that accept the same vocabulary.
            on = self._lifecycle_callables(transition.on, transition.on_refs)
            if on:
                transition_dict["on"] = on if len(on) > 1 else on[0]
            before = self._lifecycle_callables(transition.before, transition.before_refs)
            if before:
                transition_dict["before"] = before if len(before) > 1 else before[0]
            after = self._lifecycle_callables(transition.after, transition.after_refs)
            if after:
                transition_dict["after"] = after if len(after) > 1 else after[0]

            result.append(transition_dict)
        return result

    def _lifecycle_callables(self, content, refs: list) -> list:
        """Compose a transition callback slot: executable content (if any) then named refs."""
        callables: list = []
        if content and not content.is_empty:
            callables.append(ExecuteBlock(content, self._evaluator))
        callables.extend(refs)
        return callables

    def _compile_guard(self, expr):
        """Compile a guard expression (or list of them) into Cond callables."""
        if isinstance(expr, (list, tuple)):
            return [Cond.create(e, self._evaluator) for e in expr]
        return Cond.create(expr, self._evaluator)
