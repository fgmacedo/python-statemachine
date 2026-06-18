"""Load a statechart from a declarative document (SCXML, JSON or YAML).

This package is the high-level facade for building a running state machine from a document
instead of a Python class. :func:`~statemachine.io.load` is the entry point: it detects the
format (by file extension, or via an explicit ``format=``), parses the text into a neutral
intermediate representation, compiles it with a secure-by-default evaluator and returns a
ready-to-instantiate :class:`~statemachine.statemachine.StateChart` class. Every format runs
under the same execution model, so a guard, an action or a nested machine behaves identically
whether it was authored in SCXML, JSON or YAML.

Security
--------

Loading a document compiles its guards, datamodel expressions and executable content into
callables. Because a document may come from a semi-trusted source, loading is **secure by
default** (``trusted=False``): expressions are evaluated by a **restricted AST-allowlist
evaluator** that cannot reach builtins, dunder attributes, or arbitrary calls, and
``<script>`` / ``script`` (arbitrary code) is rejected. This mirrors ``yaml.safe_load`` and
keeps loading from turning into arbitrary code execution.

Passing ``trusted=True`` restores full ``eval``/``exec`` evaluation and enables ``script``.
In that mode a document is equivalent to executable Python (much like :mod:`pickle`), so
**only load ``trusted`` documents from sources you control** (hand-authored documents, the
output of your own tooling, the W3C conformance suite).

See the GHSA-v4jc-pm6r-3vj8 advisory for details.
"""

from .class_factory import ActionProtocol
from .class_factory import HistoryDefinition
from .class_factory import StateDefinition
from .class_factory import TransitionDict
from .class_factory import create_machine_class_from_definition
from .loader import build_processor
from .loader import load

__all__ = [
    "ActionProtocol",
    "TransitionDict",
    "StateDefinition",
    "HistoryDefinition",
    "create_machine_class_from_definition",
    "load",
    "build_processor",
]
