"""SCXML ingestion support.

SCXML is, per the W3C specification, *executable content*: ``cond``/``expr`` attributes and
``<script>`` elements are evaluated in the document's datamodel language. This implementation
provides a Python datamodel and loads SCXML through the same
:func:`~statemachine.io.load` facade as the native JSON/YAML formats.

Like every format, SCXML is loaded **secure by default** (``trusted=False`` rejects
``<script>`` and external ``<data src>`` / ``<invoke src>`` file references, evaluates
expressions with the restricted AST-allowlist evaluator, confines write targets to public model
attributes and magnitude-caps ``**``/``*``); pass ``trusted=True`` only for documents you
control. The parser also refuses ``<!DOCTYPE>``/DTD to block XML entity-expansion bombs. See the
security note in :mod:`statemachine.io` and the GHSA-v4jc-pm6r-3vj8, GHSA-fj3w-533r-fvf6,
GHSA-v3qq-3xvg-m77g, GHSA-4857-ggqc-p3jc and GHSA-r8gj-366q-cgvj advisories.
"""
