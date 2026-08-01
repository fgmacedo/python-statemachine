# Security: secure by default

Loading a statechart compiles its guards, datamodel expressions and executable content into
callables. A statechart is an **executable document**, not inert data, so loading one is closer
to importing code than to parsing JSON. The IO layer is **secure by default** (`trusted=False`)
so that loading a semi-trusted document does not turn into code execution or file disclosure,
but it is worth being precise about what that guarantee does and does not cover.

## Intended use, and the limits of "safe"

The primary use case for declarative loading is your **own** dynamic definitions: statecharts
produced by your application, a no-code editor you ship, your own tooling, or configuration you
control. For those, `trusted=False` is a defense-in-depth backstop.

Loading a document authored by a genuine **adversary** is a stronger threat. `trusted=False`
removes the obvious code- and file-execution vectors described below, but a statechart is still
an executable document: the most reliable protection against a hostile document is to not run
it, or to run it under OS-level isolation (see [](#availability-is-not-sandboxed)). Treat
`trusted=False` as *hardening*, not as a sandbox, and do not rely on it as your only control
for documents from parties you do not trust.

## What the guarantee covers (and what it does not)

Loading a statechart produces a **runnable machine**, not the inert data `yaml.safe_load`
returns. So the `trusted` flag is best understood as a guarantee about **confidentiality and
integrity**, not about **availability**:

- **Loading is safe (confidentiality + integrity).** With the default `trusted=False`, loading
  a document never runs arbitrary code and never reads arbitrary files. Expressions go through a
  restricted evaluator (below), `<script>` is rejected, and external resource references
  (`<data src>`, `<invoke src>`) are rejected. YAML is read with safe-load semantics and JSON
  with the stdlib parser, so a document can never instantiate arbitrary Python objects.
- **Running is not sandboxed (availability).** Once you start a machine, the document's logic
  executes. `trusted` does **not** bound how much CPU, memory or time that logic consumes. A
  malicious document can still cause denial of service. See [](#availability-is-not-sandboxed).

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

## Write targets are confined to public attributes

Actions that write to the datamodel take the destination *name* from the document:
`<assign location>`, `<foreach item>`/`index`, `<data id>` and `<send>`/`<invoke>` `idlocation`.
In every case the name must be a plain, public model attribute. Private (`_`-prefixed), dunder
(`__class__`, `__init__`, …) and engine-protected names are rejected, and for a dotted
`<assign location="a.b.c">` the check applies to **every** segment, not just the last one. This
stops a document from traversing `__class__` to corrupt the shared model class (which would
break every machine in the process) or from overwriting engine internals. As a second layer,
a live engine-capability instance (the machine, the interpreter, a core `State`/`Transition`/
`Event`, or the `_event`/`_ioprocessors` system-variable views) is also rejected as a traversed
hop or write target, so even a value that somehow referenced one cannot be used to mutate state
shared across machines. A rejected write surfaces as `error.execution`, the same as any other
action failure.

## Arithmetic is magnitude-bounded

The restricted evaluator allows arithmetic, but `**` and `*` are capped so that a tiny
expression cannot exhaust CPU or memory: an exponentiation whose result would be enormous
(`9 ** 9 ** 9`, a ~370-million-digit number) and a sequence replication that would allocate a
huge object (`[0] * 20000000`) are both rejected before they run. Ordinary scalar arithmetic
(`x * 2`, `x ** 2`) is unaffected. Under `trusted=True` the full Python evaluator is used, so
these caps do not apply.

## External resource references (`src`)

`<data src="file:…">` and `<invoke src="…">` (and `srcexpr`) read a **local file** named by the
document. Because a malicious document could point them at any file on the host and then
exfiltrate the contents (via `<log>`, `<send>` or the datamodel), they are gated exactly like
`<script>`: rejected by default, allowed only with `trusted=True`.

```py
>>> from statemachine.io import load
>>> from statemachine.exceptions import InvalidDefinition

>>> doc = """
... <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s">
...   <datamodel><data id="x" src="file:///etc/passwd"/></datamodel>
...   <state id="s"/>
... </scxml>
... """
>>> try:
...     load(doc, format="scxml")
... except InvalidDefinition:
...     print("rejected")
rejected

```

The file is never opened in the default mode: the rejection happens at load time, before any
`open()`. This also applies to a relative `src` (e.g. `src: child.yaml`), so loading a document
that includes a child from disk requires `trusted=True`.

## XML hardening

The SCXML parser refuses any `<!DOCTYPE>`/DTD. Internal entity definitions (which a DTD enables)
are the basis of *entity-expansion* denial-of-service bombs (billion laughs / quadratic blowup),
so they are rejected at parse time, independent of `trusted`:

```py
>>> bomb = """<?xml version="1.0"?>
... <!DOCTYPE scxml [<!ENTITY a "AAAAAAAAAA"><!ENTITY b "&a;&a;&a;&a;&a;">]>
... <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s"><state id="s"/></scxml>
... """
>>> try:
...     load(bomb, format="scxml")
... except InvalidDefinition:
...     print("rejected")
rejected

```

## Availability is not sandboxed

The guarantees above protect **confidentiality and integrity** of the host. They do **not** bound
the **resources** a running machine consumes. Even a document with no unsafe element can, once
started, exhaust CPU, memory or threads:

- **Eventless loops**: two states with eventless transitions between them (`a → b → a`) never
  reach a stable configuration, so a macrostep never completes.
- **`<foreach>` over a huge collection**: iterating a very large iterable.
- **Recursive `<invoke>`**: a document that invokes itself (directly or in a cycle) spawns
  unbounded child machines and threads.
- **Delayed-event accumulation**: scheduling many `<send delay="…">` events.

The state machine engine follows the SCXML run-to-completion model and intentionally does not
impose iteration, size or recursion limits. **If you load and run documents from untrusted
sources, run them under your own resource controls**: an execution timeout, and OS/process
limits on CPU, memory and threads (e.g. a subprocess with `resource` rlimits, a container, or a
watchdog that stops the machine).

## Background

This safe-by-default behaviour comes from the security advisory
[GHSA-v4jc-pm6r-3vj8](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-v4jc-pm6r-3vj8)
(CVE-2026-47103).
Before it, SCXML datamodel expressions were evaluated with `eval`, which let a malicious
document run arbitrary code on load. The restricted evaluator removes that by default across
every format (SCXML, JSON and YAML).

A set of follow-up advisories hardened the restricted mode further and prompted the
confidentiality/integrity vs availability framing above:

- [GHSA-fj3w-533r-fvf6](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-fj3w-533r-fvf6):
  `<data src="file:…">` and `<invoke src="…">` read local files during loading, regardless of
  `trusted`. Loading now rejects external `src` references unless `trusted=True`, and refuses
  `<!DOCTYPE>`/DTD to block XML entity-expansion bombs.
- [GHSA-v3qq-3xvg-m77g](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-v3qq-3xvg-m77g)
  / [GHSA-4857-ggqc-p3jc](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-4857-ggqc-p3jc):
  a document could write to a dunder/private/protected attribute (notably traversing
  `__class__`) and corrupt the shared model class process-wide. Write targets are now confined
  to public model attributes on every path segment.
- [GHSA-r8gj-366q-cgvj](https://github.com/fgmacedo/python-statemachine/security/advisories/GHSA-r8gj-366q-cgvj):
  `**`/`*` in the restricted evaluator had no magnitude bound, so a tiny expression could
  exhaust CPU or memory. They are now magnitude-capped.

These were released together in 3.2.1.
