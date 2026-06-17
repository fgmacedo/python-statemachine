"""Format-neutral runtime that turns statechart definitions into running machines.

The :class:`Interpreter` is the execution-model runtime, independent of input syntax. It
owns a :class:`~statemachine.io.builder.DefinitionBuilder` (compilation), keeps the
registry of compiled classes (``scs``, needed for ``<invoke>``), manages per-machine
sessions, injects the system variables (``_event``/``_sessionid``/``_name``/
``_ioprocessors``) on every event, coordinates invoke, and instantiates the root machine.

It is parameterized by two ports: a :class:`~statemachine.io.ports.FormatReader` (so invoke
can compile children in the same format) and an
:class:`~statemachine.io.evaluators.Evaluator` (secure by default). SCXML is just one
reader; YAML/JSON get the very same runtime behavior.
"""

import os
from typing import Any

from ..exceptions import InvalidDefinition
from ..statemachine import StateChart
from .builder import DefinitionBuilder
from .class_factory import create_machine_class_from_definition
from .evaluators import Evaluator
from .invoke import Invoker
from .model import InvokeDefinition
from .model import StateMachineDefinition
from .system_variables import IOProcessor
from .system_variables import SessionData
from .system_variables import build_system_variables
from .system_variables import create_invoke_init_callable


class Interpreter:
    """Runtime that compiles and hosts statecharts from any format.

    Args:
        reader: the format reader, used to compile invoked children in the same format.
        evaluator: the evaluation strategy for guards and executable content.
    """

    def __init__(self, *, reader, evaluator: Evaluator):
        self.reader = reader
        self._evaluator = evaluator
        self._builder = DefinitionBuilder(evaluator=evaluator, hooks=self)
        self.scs: "dict[str, type[StateChart]]" = {}
        self.sessions: dict[str, SessionData] = {}

    def process_definition(
        self, definition: StateMachineDefinition, location: str, is_invoked: bool = False
    ):
        kwargs = self._builder.build_class_kwargs(definition, is_invoked=is_invoked)
        self._add(location, kwargs)

    def start(self, **kwargs):
        self.root_cls = next(iter(self.scs.values()))
        self.root = self.root_cls(**kwargs)
        return self.root

    # -- RuntimeHooks (called back by the DefinitionBuilder) -----------------------

    def initial_enter_prefix(self, is_invoked: bool) -> list:
        # Invoked children store _invoke_session/_invoke_params before any other callback.
        if is_invoked:
            return [create_invoke_init_callable()]
        return []

    def definition_kwargs(self, definition) -> "dict[str, Any]":
        """Extra keyword arguments passed to ``create_machine_class_from_definition``.

        The three structural ``validate_*`` checks are turned **off** for loaded
        statecharts: declarative documents legitimately express configurations these
        checks would reject (states reached only through parallel regions or eventless
        paths, intentional trap/error states). The trade-off is that genuine structural
        inconsistencies are not caught at load time; see the validations reference and
        ``docs/io``. ``prepare_event`` injects the system variables for every format.
        """
        return {
            "validate_disconnected_states": False,
            "validate_trap_states": False,
            "validate_final_reachability": False,
            "start_configuration_values": list(definition.initial_states),
            "prepare_event": self._prepare_event,
        }

    def make_invoker(self, invoke_def: InvokeDefinition) -> Invoker:
        return Invoker(
            definition=invoke_def,
            base_dir=os.getcwd(),
            register_child=self._register_child,
            evaluator=self._evaluator,
        )

    # -- Runtime services ----------------------------------------------------------

    def _prepare_event(self, *args, event, **kwargs):
        machine = kwargs["machine"]
        session_data = self._get_session(machine)
        return build_system_variables(machine, session_data, event, kwargs["event_data"])

    def _get_session(self, machine) -> SessionData:
        if machine.name not in self.sessions:
            self.sessions[machine.name] = SessionData(
                processor=IOProcessor(self, machine=machine), machine=machine
            )
        return self.sessions[machine.name]

    def _register_child(self, content, child_name: str) -> type:
        """Compile and register a child statechart.

        ``content`` is either source text (parsed via this interpreter's reader, so the
        child is in the same format) or an already-parsed
        :class:`~statemachine.io.model.StateMachineDefinition` (native inline child).
        """
        if isinstance(content, StateMachineDefinition):
            definition = content
        else:
            definition = self.reader.read(content)
        self.process_definition(definition, location=child_name, is_invoked=True)
        return self.scs[child_name]

    def _add(self, location: str, definition: dict[str, Any]):
        try:
            sc_class = create_machine_class_from_definition(location, **definition)
            self.scs[location] = sc_class
            return sc_class
        except Exception as e:  # pragma: no cover
            raise InvalidDefinition(
                f"Failed to create state machine class: {e} from definition: {definition}"
            ) from e
