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

A statechart is an *executable document*, not inert data, so loading one is closer to importing
code than to parsing JSON. Because a document may come from a semi-trusted source, loading is
**secure by default** (``trusted=False``): expressions are evaluated by a **restricted
AST-allowlist evaluator** that cannot reach builtins, dunder attributes or arbitrary calls;
``<script>`` / ``script`` (arbitrary code) is rejected; external resource references
(``<data src>`` / ``<invoke src>``, which read local files) are rejected; write targets are
confined to public model attributes; and ``**``/``*`` are magnitude-capped.

Passing ``trusted=True`` restores full ``eval``/``exec`` evaluation, enables ``script`` and
allows external ``src`` references. In that mode a document is equivalent to executable Python
(much like :mod:`pickle`), so **only load ``trusted`` documents from sources you control**
(hand-authored documents, the output of your own tooling, the W3C conformance suite).

The intended use of ``trusted=False`` is your own dynamic definitions (a no-code editor, your
tooling, config you control); it is *hardening*, not a sandbox. It guarantees confidentiality
and integrity, not availability: a *running* machine can still exhaust resources (eventless
loops, large ``<foreach>``, recursive ``<invoke>``), so run genuinely untrusted documents under
your own timeout/resource limits or OS-level isolation. See the GHSA-v4jc-pm6r-3vj8,
GHSA-fj3w-533r-fvf6, GHSA-v3qq-3xvg-m77g, GHSA-4857-ggqc-p3jc and GHSA-r8gj-366q-cgvj advisories,
and ``docs/io/security.md``, for details.
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
