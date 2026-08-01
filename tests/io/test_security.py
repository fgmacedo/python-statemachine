"""Security of secure-by-default loading (GHSA-v4jc-pm6r-3vj8), unified across formats.

The restricted evaluator is shared by every format, so the same vectors run through the
:func:`~statemachine.io.load` facade for SCXML, JSON and YAML. The default (``trusted=False``)
evaluates expressions with an AST allowlist and rejects ``script``/``<script>``;
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


def _data_src_doc(src: str, fmt: str) -> str:
    """A machine whose datamodel ``x`` is loaded from an external ``src``."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<datamodel><data id="x" src="{_attr(src)}"/></datamodel>'
            '<state id="s1"><transition target="s2"/></state><final id="s2"/></scxml>'
        )
    doc = {
        "datamodel": [{"id": "x", "src": src}],
        "states": {
            "s1": {"initial": True, "transitions": [{"target": "s2"}]},
            "s2": {"final": True},
        },
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


def _invoke_src_doc(src: str, fmt: str) -> str:
    """A machine that invokes a child statechart from an external ``src``."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<state id="s1"><invoke type="scxml" src="{_attr(src)}"/></state></scxml>'
        )
    doc = {"states": {"s1": {"initial": True, "invoke": [{"type": "scxml", "src": src}]}}}
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


@pytest.mark.parametrize("fmt", FORMATS)
class TestExternalDataSrc:
    """``<data src="file:…">`` reads a local file, so it is gated like ``<script>``
    (GHSA-fj3w-533r-fvf6). The default mode rejects it at load, before opening anything."""

    def test_rejected_in_secure_mode(self, fmt, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("123")
        with pytest.raises(InvalidDefinition, match="disabled by default"):
            load(_data_src_doc(f"file://{secret}", fmt), format=fmt)

    def test_missing_file_not_opened_in_secure_mode(self, fmt):
        # The rejection happens before any open(), so a non-existent path still raises
        # InvalidDefinition (not FileNotFoundError).
        with pytest.raises(InvalidDefinition, match="disabled by default"):
            load(_data_src_doc("file:///no/such/file-xyz", fmt), format=fmt)

    def test_read_in_trusted_mode(self, fmt, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("123")
        sm = _run(_data_src_doc(f"file://{secret}", fmt), fmt, trusted=True)
        assert sm.model.x == 123

    def test_non_file_scheme_is_ignored(self, fmt):
        # Only the file scheme is resolved; other schemes are left untouched (as before),
        # so loading does not fail in secure mode.
        sm = _run(_data_src_doc("http://example.test/x", fmt), fmt)
        assert sm.model.x is None


@pytest.mark.parametrize("fmt", FORMATS)
class TestExternalInvokeSrc:
    """``<invoke src="…">`` reads (and runs) a child document from disk; a static ``src``
    is rejected at load, mirroring ``<data src>`` (GHSA-fj3w-533r-fvf6)."""

    def test_rejected_in_secure_mode(self, fmt):
        with pytest.raises(InvalidDefinition, match="disabled by default"):
            load(_invoke_src_doc("file:///some/child", fmt), format=fmt)

    def test_relative_src_rejected_in_secure_mode(self, fmt):
        # The strict policy blocks any external src, including a confined relative path.
        with pytest.raises(InvalidDefinition, match="disabled by default"):
            load(_invoke_src_doc("child.scxml", fmt), format=fmt)

    def test_allowed_in_trusted_mode(self, fmt):
        # The invoker is built at load time, so loading under trusted=True is enough to
        # exercise the gate (a no-op); no need to instantiate and run the invoke.
        load(_invoke_src_doc("file:///some/child", fmt), format=fmt, trusted=True)


class TestXMLEntityExpansion:
    """A DOCTYPE/DTD enables internal-entity expansion bombs (billion laughs); the SCXML
    parser refuses it at parse time, independent of the trust level."""

    BOMB = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE scxml [<!ENTITY a "AAAAAAAAAA"><!ENTITY b "&a;&a;&a;&a;&a;">]>'
        '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
        '<datamodel><data id="x" expr="\'&b;\'"/></datamodel>'
        '<state id="s1"><transition target="s2"/></state><final id="s2"/></scxml>'
    )

    @pytest.mark.parametrize("trusted", [False, True])
    def test_doctype_rejected(self, trusted):
        with pytest.raises(InvalidDefinition, match="DOCTYPE"):
            load(self.BOMB, format="scxml", trusted=trusted)


class TestAssignLocationTraversal:
    """``<assign location>`` must not walk into private/dunder objects, even on an
    intermediate hop (only the final attribute was guarded before). The traversal guard
    raises, which the engine routes to ``error.execution``."""

    class Model:
        def __init__(self):
            import types as _types

            self.public = type("Box", (), {"value": 0})()
            self._private = type("Box", (), {"value": 0})()
            self.a_class = type("Box", (), {"value": 0})
            self.a_module = _types.ModuleType("fake_module")

    @staticmethod
    def _assign(location: str, model):
        doc = (
            "states:\n"
            "  start:\n"
            "    initial: true\n"
            "    transitions: [{event: go, target: s1}]\n"
            "  s1:\n"
            f'    enter: [{{assign: {{location: "{location}", expr: "1"}}}}]\n'
            "    transitions: [{event: error.execution, target: failed}]\n"
            "  failed: {final: true}\n"
        )
        sm = load(doc, format="yaml")(model=model)
        sm.send("go")
        return _config(sm)

    def test_public_intermediate_allowed(self):
        model = self.Model()
        assert "s1" in self._assign("public.value", model)
        assert model.public.value == 1

    def test_private_intermediate_rejected(self):
        model = self.Model()
        assert "failed" in self._assign("_private.value", model)
        assert model._private.value == 0  # never written

    def test_dunder_intermediate_rejected(self):
        model = self.Model()
        assert "failed" in self._assign("public.__class__.value", model)
        assert type(model.public).value == 0  # class object not corrupted (would be 1 if written)

    def test_class_valued_attribute_rejected(self):
        # Even reached via a public name, a class is never a valid write target (Defense B).
        model = self.Model()
        assert "failed" in self._assign("a_class.value", model)
        assert model.a_class.value == 0  # shared class not corrupted

    def test_module_valued_attribute_rejected(self):
        # A module is likewise rejected as a hop/write target (Defense B).
        model = self.Model()
        assert "failed" in self._assign("a_module.value", model)
        assert not hasattr(model.a_module, "value")  # module not mutated


def _exec_doc(enter_scxml: str, enter_native: list, fmt: str) -> str:
    """A machine that runs executable content on entering ``s1`` (reached via ``go``).

    A datamodel ``x`` is predeclared so ``<assign location="x">`` is a valid target, and
    ``error.execution`` is routed to a ``failed`` final state so a rejected action is
    observable.
    """
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="start">'
            '<datamodel><data id="x" expr="0"/></datamodel>'
            '<state id="start"><transition event="go" target="s1"/></state>'
            f'<state id="s1"><onentry>{enter_scxml}</onentry>'
            '<transition event="error.execution" target="failed"/></state>'
            '<final id="failed"/></scxml>'
        )
    doc = {
        "datamodel": [{"id": "x", "expr": "0"}],
        "states": {
            "start": {"initial": True, "transitions": [{"event": "go", "target": "s1"}]},
            "s1": {
                "enter": enter_native,
                "transitions": [{"event": "error.execution", "target": "failed"}],
            },
            "failed": {"final": True},
        },
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


def _run_exec(enter_scxml: str, enter_native: list, fmt: str):
    sm = load(_exec_doc(enter_scxml, enter_native, fmt), format=fmt)()
    sm.send("go")
    return sm


# Names a document must never be allowed to write to: dunder (class rebind / sandbox escape),
# private (``_``-prefixed), or engine-protected (GHSA-v3qq-3xvg-m77g, GHSA-4857-ggqc-p3jc).
BAD_WRITE_NAMES = ["__class__", "_secret", "state"]


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("name", BAD_WRITE_NAMES)
class TestWriteTargetGuard:
    """Every document-controlled write target rejects a private, dunder or engine-protected
    name and routes to ``error.execution``. The guard lives in the shared ``actions.py``, so
    it holds identically for SCXML, JSON and YAML."""

    def test_assign_location(self, fmt, name):
        sm = _run_exec(
            f'<assign location="{_attr(name)}" expr="1"/>',
            [{"assign": {"location": name, "expr": "1"}}],
            fmt,
        )
        assert "failed" in _config(sm)

    def test_foreach_item(self, fmt, name):
        sm = _run_exec(
            f'<foreach item="{_attr(name)}" array="[1]"><log expr="1"/></foreach>',
            [{"foreach": {"item": name, "array": "[1]", "do": [{"log": "1"}]}}],
            fmt,
        )
        assert "failed" in _config(sm)

    def test_foreach_index(self, fmt, name):
        sm = _run_exec(
            f'<foreach item="ok" index="{_attr(name)}" array="[1]"><log expr="1"/></foreach>',
            [{"foreach": {"item": "ok", "index": name, "array": "[1]", "do": [{"log": "1"}]}}],
            fmt,
        )
        assert "failed" in _config(sm)

    def test_send_idlocation(self, fmt, name):
        sm = _run_exec(
            f'<send event="e" idlocation="{_attr(name)}"/>',
            [{"send": {"event": "e", "idlocation": name}}],
            fmt,
        )
        assert "failed" in _config(sm)


@pytest.mark.parametrize("fmt", FORMATS)
class TestAssignClassPollution:
    """The reported process-wide vector: ``<assign location="__class__.pwned">`` would
    ``setattr`` on the *shared* model class, corrupting every machine in the process. The
    traversal guard rejects it (GHSA-v3qq-3xvg-m77g)."""

    def test_shared_model_class_not_corrupted(self, fmt):
        from statemachine.model import Model

        assert not hasattr(Model, "pwned")
        sm = _run_exec(
            '<assign location="__class__.pwned" expr="1"/>',
            [{"assign": {"location": "__class__.pwned", "expr": "1"}}],
            fmt,
        )
        assert "failed" in _config(sm)
        assert not hasattr(Model, "pwned")  # shared class intact, process-wide


#: The live engine-capability objects the restricted evaluator must never hand to an
#: untrusted expression (they are exactly ``statemachine.event._event_data_kwargs``).
ENGINE_OBJECTS = [
    "machine",
    "model",
    "event",
    "event_data",
    "transition",
    "state",
    "source",
    "target",
]


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("name", ENGINE_OBJECTS)
class TestEngineObjectsWithheld:
    """The restricted evaluator withholds the live engine objects (``machine``, ``model``,
    ``event``, ...) from name resolution: a bare value expression naming one raises NameError,
    which the engine contains as ``error.execution`` (GHSA-v3qq-3xvg-m77g). Trusted mode is
    unaffected, so a trusted document can still reference them."""

    def test_rejected_in_secure_mode(self, fmt, name):
        sm = _run_exec(
            f'<assign location="x" expr="{_attr(name)}"/>',
            [{"assign": {"location": "x", "expr": name}}],
            fmt,
        )
        assert "failed" in _config(sm)

    def test_resolvable_in_trusted_mode(self, fmt, name):
        # Under trusted=True the object resolves (legacy eval namespace); no error.execution.
        doc = _exec_doc(
            f'<assign location="x" expr="{_attr(name)}"/>',
            [{"assign": {"location": "x", "expr": name}}],
            fmt,
        )
        sm = load(doc, format=fmt, trusted=True)()
        sm.send("go")
        assert "failed" not in _config(sm)


@pytest.mark.parametrize("fmt", ["yaml", "scxml"])
class TestLeakedEngineClassPollution:
    """The reported bypass: store the live engine (``machine``) in a public model slot, then
    traverse it to a shared exception class and ``setattr`` a public name onto it, mutating
    that class process-wide. Both defenses close it: the engine object is withheld from the
    expression (Defense A), and even a leaked class/module is rejected as an assign hop or
    write target (Defense B). Asserted to route to ``error.execution`` and to leave the shared
    class untouched (GHSA-v3qq-3xvg-m77g)."""

    def test_shared_exception_class_not_corrupted(self, fmt):
        from statemachine.exceptions import TransitionNotAllowed

        had_own = "add_note" in TransitionNotAllowed.__dict__
        scxml = (
            '<assign location="x" expr="machine"/>'
            '<assign location="x.TransitionNotAllowed.add_note" expr="1"/>'
        )
        native = [
            {"assign": {"location": "x", "expr": "machine"}},
            {"assign": {"location": "x.TransitionNotAllowed.add_note", "expr": "1"}},
        ]
        try:
            sm = _run_exec(scxml, native, fmt)
            assert "failed" in _config(sm)
            # The shared class is intact: add_note is still the inherited method, not int 1,
            # and a normal exception still constructs and carries a note.
            assert callable(TransitionNotAllowed.add_note)
            err = TransitionNotAllowed(None, set())
            err.add_note("still works")
        finally:
            # Defensive: if a regression ever mutated the shared class, restore it so the
            # rest of the suite is not corrupted.
            if not had_own and "add_note" in TransitionNotAllowed.__dict__:
                del TransitionNotAllowed.add_note


def _data_id_doc(data_id: str, fmt: str) -> str:
    """A machine whose datamodel declares a single ``<data>`` with the given id."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1">'
            f'<datamodel><data id="{_attr(data_id)}" expr="1"/></datamodel>'
            '<state id="s1"/></scxml>'
        )
    doc = {"datamodel": [{"id": data_id, "expr": "1"}], "states": {"s1": {"initial": True}}}
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


@pytest.mark.parametrize("fmt", FORMATS)
class TestDataIdGuard:
    """A ``<data id>`` names a model attribute. A private/dunder/protected id is rejected
    during datamodel initialization (contained), so it never lands on the model."""

    def test_private_id_not_written(self, fmt):
        sm = load(_data_id_doc("_secret", fmt), format=fmt)()
        assert not hasattr(sm.model, "_secret")

    def test_dunder_id_does_not_rebind_class(self, fmt):
        from statemachine.model import Model

        sm = load(_data_id_doc("__class__", fmt), format=fmt)()
        assert type(sm.model) is Model


def _dos_expr_scxml(expr: str) -> str:
    return f'<assign location="x" expr="{_attr(expr)}"/>'


@pytest.mark.parametrize("fmt", FORMATS)
class TestArithmeticDoS:
    """``**`` and ``*`` are magnitude-capped in the restricted evaluator: the denial-of-service
    forms are rejected, but ordinary scalar arithmetic keeps working (GHSA-r8gj-366q-cgvj)."""

    @pytest.mark.parametrize("expr", ["9**9**9", "2**100000", "[0]*20000000", "'a'*20000000"])
    def test_dos_expr_rejected(self, fmt, expr):
        # The cap raises while evaluating the expression, surfacing as error.execution.
        sm = _run_exec(
            _dos_expr_scxml(expr),
            [{"assign": {"location": "x", "expr": expr}}],
            fmt,
        )
        assert "failed" in _config(sm)

    def test_scalar_arithmetic_preserved(self, fmt):
        sm = _run_exec(
            _dos_expr_scxml("x * 2 + 3 ** 2"),
            [{"assign": {"location": "x", "expr": "x * 2 + 3 ** 2"}}],
            fmt,
        )
        assert "failed" not in _config(sm)
        assert sm.model.x == 9  # 0 * 2 + 3 ** 2


@pytest.mark.parametrize("fmt", FORMATS)
class TestSystemVariableFacadeLeak:
    """Second-round finding (GHSA-v3qq-3xvg-m77g): the ``_``-prefixed SCXML system-variable
    facades (``_event`` / ``_ioprocessors``) must not re-expose the machine, interpreter or a
    shared State through public attribute chains. Each reviewer PoC mutates a process-shared
    object across sibling instances of the same loaded class; the source is now sanitized so
    the attack routes to ``error.execution`` and leaves the shared object untouched. A
    ``finally`` restores the shared object so a regression cannot corrupt the rest of the suite.
    """

    def test_route1_interpreter_via_ioprocessors(self, fmt):
        # Route 1: reach the shared Interpreter via _ioprocessors.interpreter, then setattr its
        # sessions dict; on 5218687 this silently broke every sibling instance.
        cls = load(
            _exec_doc(
                '<assign location="x" expr="_ioprocessors.interpreter"/>'
                '<assign location="x.sessions" expr="0"/>',
                [
                    {"assign": {"location": "x", "expr": "_ioprocessors.interpreter"}},
                    {"assign": {"location": "x.sessions", "expr": "0"}},
                ],
                fmt,
            ),
            format=fmt,
        )
        interpreter = cls._io_processor
        original_sessions = interpreter.sessions
        try:
            sm = cls()
            sm.send("go")
            assert "failed" in _config(sm)
            # x never became the interpreter, so its sessions dict is the same object, intact.
            assert interpreter.sessions is original_sessions
            assert isinstance(interpreter.sessions, dict)
            # x holds the untouched datamodel default, not a live Interpreter.
            assert sm.model.x == 0
        finally:
            interpreter.sessions = original_sessions

    def test_route2_machine_and_state_via_event(self, fmt):
        # Route 2: reach the machine (and from it a shared State) via _event.trigger_data.machine.
        cls = load(
            _exec_doc(
                '<assign location="x" expr="_event.trigger_data.machine"/>',
                [{"assign": {"location": "x", "expr": "_event.trigger_data.machine"}}],
                fmt,
            ),
            format=fmt,
        )
        shared_state = cls.states_map["s1"]  # class-level State, shared across instances
        original_name = shared_state.name
        try:
            sm = cls()
            sm.send("go")
            assert "failed" in _config(sm)
            assert shared_state.name == original_name  # shared State not renamed
            assert sm.model.x == 0  # x never became the machine
        finally:
            shared_state.name = original_name


#: Bare value expressions that reached an engine object through a facade on 5218687. All must
#: be contained as ``error.execution`` (the attribute no longer resolves in restricted mode).
FACADE_LEAK_EXPRS = [
    "_ioprocessors.interpreter",
    "_ioprocessors.machine",
    "_event.trigger_data",
    "_event.event_data",
    "_event.machine",
]


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("expr", FACADE_LEAK_EXPRS)
class TestFacadeBareExprRejected:
    """A bare expression that walks a facade to an engine object no longer resolves in
    restricted mode: the attribute is gone (renamed private) and no ``__getattr__`` forwards
    it, so evaluation raises AttributeError, contained as ``error.execution``."""

    def test_rejected_in_secure_mode(self, fmt, expr):
        sm = _run_exec(
            f'<assign location="x" expr="{_attr(expr)}"/>',
            [{"assign": {"location": "x", "expr": expr}}],
            fmt,
        )
        assert "failed" in _config(sm)


def _visible_surface_doc(fmt: str) -> str:
    """A machine that copies SCXML-visible ``_event`` fields into the datamodel on ``go``."""
    if fmt == "scxml":
        return (
            '<scxml xmlns="http://www.w3.org/2005/07/scxml" initial="start">'
            '<datamodel><data id="n" expr="0"/><data id="t" expr="0"/>'
            '<data id="p" expr="0"/></datamodel>'
            '<state id="start"><transition event="go" target="s1"/></state>'
            '<state id="s1"><onentry>'
            '<assign location="n" expr="_event.name"/>'
            '<assign location="t" expr="_event.type"/>'
            '<assign location="p" expr="_event.data.aParam"/>'
            "</onentry></state></scxml>"
        )
    doc = {
        "datamodel": [
            {"id": "n", "expr": "0"},
            {"id": "t", "expr": "0"},
            {"id": "p", "expr": "0"},
        ],
        "states": {
            "start": {"initial": True, "transitions": [{"event": "go", "target": "s1"}]},
            "s1": {
                "enter": [
                    {"assign": {"location": "n", "expr": "_event.name"}},
                    {"assign": {"location": "t", "expr": "_event.type"}},
                    {"assign": {"location": "p", "expr": "_event.data.aParam"}},
                ]
            },
        },
    }
    return json.dumps(doc) if fmt == "json" else yaml.safe_dump(doc)


@pytest.mark.parametrize("fmt", FORMATS)
class TestFacadeVisibleSurfacePreserved:
    """Sanitizing the facades keeps the SCXML-visible surface working in restricted mode:
    ``_event.name`` / ``_event.type`` / ``_event.data`` / ``_event.data.<field>`` still resolve.
    """

    def test_event_fields_resolve(self, fmt):
        sm = load(_visible_surface_doc(fmt), format=fmt)()
        sm.send("go", aParam=7)
        assert "s1" in _config(sm)
        assert sm.model.n == "go"
        assert sm.model.t == "external"
        assert sm.model.p == 7


class TestEngineInstanceWriteTargetRejected:
    """Sink hardening (Defense B): even if a public alias ever leaked a live engine object as a
    value, ``<assign>`` rejects it as a traversed hop or write target, so it cannot be pivoted
    onto shared state. Built directly by placing engine instances in public model slots."""

    class Model:
        def __init__(self):
            from statemachine.event import Event
            from statemachine.state import State
            from statemachine.transition import Transition

            self.a_state = State("run")
            self.an_event = Event("go")
            self.a_transition = Transition(State("a"), State("b"), event="go")

    @staticmethod
    def _assign(location: str, model):
        doc = (
            "states:\n"
            "  start:\n"
            "    initial: true\n"
            "    transitions: [{event: go, target: s1}]\n"
            "  s1:\n"
            f'    enter: [{{assign: {{location: "{location}", expr: "1"}}}}]\n'
            "    transitions: [{event: error.execution, target: failed}]\n"
            "  failed: {final: true}\n"
        )
        sm = load(doc, format="yaml")(model=model)
        sm.send("go")
        return _config(sm)

    def test_state_instance_rejected(self):
        model = self.Model()
        assert "failed" in self._assign("a_state.name", model)
        assert model.a_state.name == "run"  # shared State not renamed

    def test_event_instance_rejected(self):
        model = self.Model()
        assert "failed" in self._assign("an_event.pwned", model)
        assert not hasattr(model.an_event, "pwned")  # engine Event not mutated

    def test_transition_instance_rejected(self):
        model = self.Model()
        assert "failed" in self._assign("a_transition.pwned", model)
        assert not hasattr(model.a_transition, "pwned")  # engine Transition not mutated

    def test_machine_instance_rejected(self):
        # The machine (StateChart) reached as a value is rejected as a write target too.
        doc = (
            "states:\n"
            "  start:\n"
            "    initial: true\n"
            "    transitions: [{event: go, target: s1}]\n"
            "  s1:\n"
            '    enter: [{assign: {location: "leaked.name", expr: "1"}}]\n'
            "    transitions: [{event: error.execution, target: failed}]\n"
            "  failed: {final: true}\n"
        )
        model = type("Model", (), {})()
        sm = load(doc, format="yaml")(model=model)
        model.leaked = sm  # a public alias to the live machine
        original_name = sm.name
        sm.send("go")
        assert "failed" in _config(sm)
        assert sm.name == original_name  # machine not mutated
