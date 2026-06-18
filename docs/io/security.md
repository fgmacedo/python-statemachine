# Security: secure by default

Loading a statechart compiles its guards, datamodel expressions and executable content into
callables. Because a document can come from an untrusted source, the IO layer is **secure by
default**, mirroring the discipline of `yaml.safe_load`.

The `trusted` flag controls only **expression and script evaluation**. Document parsing is
always safe: YAML is read with safe-load semantics and JSON with the stdlib parser, so a
document can never instantiate arbitrary Python objects, regardless of `trusted`.

## The two evaluation modes

`load(..., trusted=False)` (the default) uses a **restricted evaluator** built on an AST
allowlist. It allows the everyday building blocks of a guard or expression:

- comparisons (`==`, `!=`, `<`, `>=`, …) and boolean algebra (`and`, `or`, `not`);
- arithmetic, indexing (`items[0]`), and list/tuple/set/dict literals;
- reading attributes, **including property getters** (`order.is_ready`);
- the `In(state_id)` predicate for testing the active configuration.

It refuses anything that could escape the sandbox:

- function and method calls (the only exception is `In(...)`);
- builtins (`len`, `open`, `__import__`, …), lambdas and comprehensions;
- dunder or private attribute access (`x.__class__`, `x._secret`).

A rejected expression fails **at load time** with `InvalidDefinition`, not later at runtime:

```py
>>> from statemachine.io import load
>>> from statemachine.exceptions import InvalidDefinition

>>> doc = """
... states:
...   s:
...     initial: true
...     transitions:
...       - {event: go, target: s, cond: "escape_to_shell()"}
... """
>>> try:
...     load(doc, format="yaml")
... except InvalidDefinition:
...     print("rejected")
rejected

```

What the allowlist refuses is **call syntax** (`name()`, `obj.method()`), so an attacker's
expression cannot reach builtins, the one exception being `In(...)`:

- `cond: "order.is_ready"` — allowed (a plain attribute read, which runs the property getter).
- `cond: "order.is_ready()"` — rejected (call syntax).

Guards (`cond`/`unless`) have one extra affordance, matching class-defined guards: a bare name
that resolves to a model **method** is invoked by name, like a callback reference, receiving
the event's keyword arguments. That is still safe, it runs the integrator's own method named
in the document, not arbitrary code, so guard logic can be a property, an attribute or a
method without `trusted=True`.

## What `trusted=True` unlocks

`load(..., trusted=True)` evaluates expressions as full Python (`eval`) and enables the
`script` action (`exec`). Concretely, it adds exactly what the restricted mode withholds:

- method calls and builtins inside guards and expressions (`len(cart)`, `order.is_ready()`,
  `_event.data.get("x")`);
- the `script` action, a block of Python statements that reads and writes the model.

Everything else, the `assign`, `raise`, `send`, `log`, `foreach`, `cancel` and `if` actions,
already works in both modes; `script` is the only action gated behind `trusted`. Errors in
trusted expressions surface at runtime (as `error.execution`) rather than at load time.

Use `trusted=True` **only** for documents you fully control.

## Background

This safe-by-default behaviour comes from the security advisory
[GHSA-v4jc-pm6r-3vj8](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-v4jc-pm6r-3vj8)
(CVE-2026-47103).
Before it, SCXML datamodel expressions were evaluated with `eval`, which let a malicious
document run arbitrary code on load. The restricted evaluator removes that by default across
every format (SCXML, JSON and YAML).
