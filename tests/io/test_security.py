"""Security of secure-by-default loading (GHSA-v4jc-pm6r-3vj8), unified across formats.

The restricted evaluator is shared by every format, so the same vectors run through the
:func:`~statemachine.io.load` facade for SCXML, JSON and YAML. The default (``trusted=False``)
evaluates expressions with an AST whitelist and rejects ``script``/``<script>``;
``trusted=True`` restores ``eval``/``exec``. Concerns that need a bound Python model (the
guard name-resolution boundary) live in their own class at the end.
"""

import json
from xml.sax.saxutils import escape as xml_escape

import pytest
import yaml
from statemachine.exceptions import InvalidDefinition
from statemachine.io import load

FORMATS = ["yaml", "json", "scxml"]

# Expressions that try to escape the sandbox; all must be rejected at load (parse) time.
ESCAPE_VECTORS = [
    "__import__('os').system('id')",
    "().__class__.__bases__",
    "[].__class__",
    "(lambda: 1)()",
    "[y for y in [1, 2]]",
    "x.bit_length()",
]


def _attr(expr: str) -> str:
    return xml_escape(expr, {'"': "&quot;"})


def _cond_doc(expr: str, fmt: str) -> str:
    """A machine whose first (eventless) transition is guarded by ``expr``."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<state id="s1"><transition cond="{_attr(expr)}" target="s2"/>'
            '<transition target="s3"/></state><final id="s2"/><final id="s3"/></scxml>'
        )
    doc = {
        "states": {
            "s1": {
                "initial": True,
                "transitions": [{"target": "s2", "cond": expr}, {"target": "s3"}],
            },
            "s2": {"final": True},
            "s3": {"final": True},
        }
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


def _data_doc(expr: str, fmt: str) -> str:
    """A machine that assigns ``x = expr`` in its datamodel."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<datamodel><data id="x" expr="{_attr(expr)}"/></datamodel>'
            '<state id="s1"><transition target="s2"/></state><final id="s2"/></scxml>'
        )
    doc = {
        "datamodel": [{"id": "x", "expr": expr}],
        "states": {
            "s1": {"initial": True, "transitions": [{"target": "s2"}]},
            "s2": {"final": True},
        },
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


def _script_doc(body: str, fmt: str) -> str:
    """A machine that runs ``body`` as a ``script`` on entry."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<state id="s1"><onentry><script>{body}</script></onentry>'
            '<transition target="s2"/></state><final id="s2"/></scxml>'
        )
    doc = {
        "states": {
            "s1": {
                "initial": True,
                "enter": [{"script": body}],
                "transitions": [{"target": "s2"}],
            },
            "s2": {"final": True},
        }
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


def _run(doc: str, fmt: str, *, trusted: bool = False):
    return load(doc, format=fmt, trusted=trusted)()


def _config(sm):
    return {s.id for s in sm.configuration}


@pytest.mark.parametrize("fmt", FORMATS)
class TestSecureModeAllows:
    """Legitimate expressivity needs no ``trusted=True``."""

    def test_comparison_guard(self, fmt):
        assert "s2" in _config(_run(_cond_doc("1 < 2", fmt), fmt))
        assert "s3" in _config(_run(_cond_doc("1 > 2", fmt), fmt))

    def test_in_predicate(self, fmt):
        assert "s2" in _config(_run(_cond_doc("In('s1')", fmt), fmt))

    def test_arithmetic_datamodel(self, fmt):
        assert _run(_data_doc("2 + 3", fmt), fmt).model.x == 5


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("expr", ESCAPE_VECTORS)
class TestEscapeRejected:
    """Sandbox-escape expressions are rejected at load time, before anything runs."""

    def test_rejected_in_guard(self, expr, fmt):
        with pytest.raises(InvalidDefinition):
            load(_cond_doc(expr, fmt), format=fmt)

    def test_rejected_in_datamodel(self, expr, fmt):
        with pytest.raises(InvalidDefinition):
            load(_data_doc(expr, fmt), format=fmt)


@pytest.mark.parametrize("fmt", FORMATS)
class TestScript:
    def test_rejected_in_secure_mode(self, fmt):
        with pytest.raises(InvalidDefinition, match="script"):
            load(_script_doc("x = 1", fmt), format=fmt)

    def test_runs_in_trusted_mode(self, fmt):
        sm = _run(_script_doc('greeting = "hi"', fmt), fmt, trusted=True)
        assert sm.model.greeting == "hi"


@pytest.mark.parametrize("fmt", FORMATS)
class TestTrustedRestoresArbitrary:
    def test_arbitrary_expression(self, fmt):
        sm = _run(_data_doc("[].__class__.__name__", fmt), fmt, trusted=True)
        assert sm.model.x == "list"


@pytest.mark.parametrize("fmt", FORMATS)
class TestRuntimeErrorsContained:
    """A runtime evaluation error becomes ``error.execution``, never a crash."""

    def test_undefined_name_is_caught(self, fmt):
        if fmt == "scxml":
            doc = (
                '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
                '<datamodel><data id="x" expr="0"/></datamodel>'
                '<state id="s1"><onentry><assign location="x" expr="missing + 1"/></onentry>'
                '<transition event="error.execution" target="s2"/></state><final id="s2"/></scxml>'
            )
        else:
            d = {
                "datamodel": [{"id": "x", "expr": "0"}],
                "states": {
                    "s1": {
                        "initial": True,
                        "enter": [{"assign": {"location": "x", "expr": "missing + 1"}}],
                        "transitions": [{"event": "error.execution", "target": "s2"}],
                    },
                    "s2": {"final": True},
                },
            }
            doc = json.dumps(d) if fmt == "json" else yaml.safe_dump(d)
        assert "s2" in _config(_run(doc, fmt))


class TestGuardNameResolutionBoundary:
    """A guard binds names against the model. A method is called (parity with the Python
    dialect), but the secure boundary still holds: private/dunder names and builtins never
    resolve, so a document cannot read the model's internals or walk the object graph."""

    @staticmethod
    def _guard(cond, model):
        doc = (
            "states:\n"
            "  a:\n"
            "    initial: true\n"
            "    transitions:\n"
            f'      - {{event: go, target: hit, cond: "{cond}"}}\n'
            "      - {event: go, target: miss}\n"
            "  hit: {final: true}\n"
            "  miss: {final: true}\n"
        )
        sm = load(doc, format="yaml")(model=model)
        sm.send("go")
        return next(iter(_config(sm)))

    class Model:
        def __init__(self):
            self._secret = "TOPSECRET"
            self.flag = True

        def allow(self):
            return True

    def test_model_method_is_called(self):
        assert self._guard("allow", self.Model()) == "hit"

    def test_public_attribute_is_read(self):
        assert self._guard("flag", self.Model()) == "hit"

    @pytest.mark.parametrize("name", ["_secret", "__class__", "__init__", "open", "eval"])
    def test_private_dunder_and_builtins_do_not_resolve(self, name):
        # None reach the model internals or builtins: the guard evaluates falsy (NameError
        # contained) and the transition is not taken.
        assert self._guard(name, self.Model()) == "miss"


class TestSCXMLSpecific:
    """Concerns tied to SCXML's XML syntax, with no native equivalent."""

    def test_top_level_script_rejected_in_secure_mode(self):
        doc = (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            "<script>y = 2</script>"
            '<state id="s1"><transition target="s2"/></state><final id="s2"/></scxml>'
        )
        with pytest.raises(InvalidDefinition, match="script"):
            load(doc, format="scxml")
