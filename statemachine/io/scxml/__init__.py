"""SCXML ingestion support.

SCXML is, per the W3C specification, *executable content*: ``cond``/``expr`` attributes and
``<script>`` elements are evaluated in the document's datamodel language. This implementation
provides a Python datamodel and loads SCXML through the same
:func:`~statemachine.io.load` facade as the native JSON/YAML formats.

Like every format, SCXML is loaded **secure by default** (``trusted=False`` rejects
``<script>`` and evaluates expressions with the restricted AST-whitelist evaluator); pass
``trusted=True`` only for documents you control. See the security note in
:mod:`statemachine.io` and the GHSA-v4jc-pm6r-3vj8 advisory.
"""
