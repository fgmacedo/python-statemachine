"""Back-compatible SCXML entry point: a preconfigured neutral Interpreter.

The runtime is the format-neutral :class:`~statemachine.io.interpreter.Interpreter`.
``SCXMLProcessor`` is simply that interpreter wired with the SCXML reader and the
trusted/restricted evaluator, plus the ``parse_scxml`` convenience for parsing a document
from a string. New code should prefer :func:`statemachine.io.load` (which also reads files
and detects the format from the extension).
"""

from ..evaluators import evaluator_for
from ..interpreter import Interpreter
from .reader import SCXMLReader
from .reader import parse_scxml


class SCXMLProcessor(Interpreter):
    """Parses SCXML documents into :class:`~statemachine.statemachine.StateChart` classes.

    Args:
        trusted: when ``False`` (default), datamodel expressions are evaluated by
            a restricted AST-allowlist evaluator and ``<script>`` is rejected, so
            loading a document cannot execute arbitrary code. When ``True``,
            expressions and ``<script>`` are evaluated as arbitrary Python via
            ``eval``/``exec`` — only use it for SCXML you trust (see the package
            docstring and GHSA-v4jc-pm6r-3vj8).
    """

    def __init__(self, trusted: bool = False):
        super().__init__(reader=SCXMLReader(), evaluator=evaluator_for(trusted))

    def parse_scxml(self, sm_name: str, scxml_content: str):
        definition = parse_scxml(scxml_content)
        self.process_definition(definition, location=definition.name or sm_name)
