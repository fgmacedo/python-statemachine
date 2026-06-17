# IO and formats

`python-statemachine` can build a statechart from a declarative document instead of a
Python class. Reach for this when the machine's shape comes from outside your code: a
configuration file, a no-code editor, a definition shared across services, or a document
produced by a tool or an LLM. Three formats are supported out of the box:

| Format | Extensions | Notes |
|---|---|---|
| JSON | `.json` | Native declarative syntax (stdlib, no extra dependency). |
| YAML | `.yaml`, `.yml` | Native declarative syntax (requires the `[yaml]` extra). |
| SCXML | `.scxml`, `.xml` | W3C State Chart XML, the standard this library's execution model follows. |

JSON and YAML are two serializations of the same native syntax; SCXML is the W3C XML
standard you can also load. Whichever you pick, you get the same machine and the same
execution model, so a guard, an action or a nested machine behaves identically across
formats.

This section is about **how to express the library's features in a document**. It does not
re-teach what those features mean: for the concepts themselves, follow the core guides.

| To express… | …see |
|---|---|
| States, hierarchy, parallel regions, history | [](../states.md) |
| Transitions, self/internal, eventless | [](../transitions.md) |
| Guards (`cond`/`unless`) | [](../guards.md) |
| Actions and callback naming conventions | [](../actions.md) |
| Events and how to send them | [](../events.md), [](../statechart.md) |
| Nested machines (`invoke`) | [](../invoke.md) |
| Run-to-completion processing | [](../processing_model.md) |

The pages here cover the declarative side: [](formats.md) for the native vocabulary,
[](json_schema.md) for validating a document, and [](security.md) for what `trusted` does.

## The `load` facade

{func}`statemachine.io.load` is the entry point. Give it a file path (the format is
detected from the extension) or inline content (with an explicit `format`), and it returns
a ready-to-instantiate {class}`~statemachine.statemachine.StateChart` class:

```py
>>> from statemachine.io import load

>>> Toggle = load(
...     """
...     name: Toggle
...     states:
...       lit:
...         initial: true
...         transitions:
...           - {event: flip, target: dark}
...       dark:
...         transitions:
...           - {event: flip, target: lit}
...     """,
...     format="yaml",
...     validate=True,
... )

>>> sm = Toggle()
>>> "lit" in sm.configuration_values
True
>>> _ = sm.send("flip")
>>> sorted(sm.configuration_values)
['dark']

```

Loading from a file detects the format automatically:

```py
>>> from pathlib import Path
>>> import tempfile

>>> path = Path(tempfile.mkdtemp()) / "toggle.json"
>>> _ = path.write_text(
...     '{"states": {"a": {"initial": true, "transitions": [{"event": "go", "target": "b"}]}, "b": {}}}'
... )
>>> Machine = load(path, validate=True)
>>> sm = Machine()
>>> _ = sm.send("go")
>>> sorted(sm.configuration_values)
['b']

```

The returned class is an ordinary `StateChart`: instantiate it, bind a `model`, add
listeners, and send events exactly as you would a hand-written machine (see
[](../statechart.md)).

## Secure by default

`load` is **secure by default**: guard and datamodel expressions are evaluated by a
restricted evaluator that cannot reach builtins, attribute dunders, or arbitrary calls, and
`script` / raw Python is rejected. Pass `trusted=True` only for documents you control. See
[](security.md).

## Validation of loaded documents

Statecharts built from a Python class are checked for three structural problems at
definition time: [unreachable states](../validations.md#unreachable-states),
[trap states](../validations.md#trap-states), and
[final-state reachability](../validations.md#final-state-reachability). For **loaded**
documents these three checks are turned **off** (`validate_disconnected_states`,
`validate_trap_states` and `validate_final_reachability` are all `False`).

These formats can legitimately express configurations those checks would reject: states
reached only through parallel regions or eventless paths, intentional trap/error states,
finals reachable only at runtime. Leaving the checks on would flag valid documents as
invalid. The trade-off is that a genuine structural mistake in a loaded document is not
reported at load time. To get those guarantees back, validate the document against the
[JSON Schema](json_schema.md) and/or assert the machine's structure in your own tests.

## Multiple machines in one document

A single document can define or `invoke` more than one machine. `load` returns the root
class and keeps the others reachable through it. When you need to reach every compiled
machine directly, use {func}`statemachine.io.build_processor`:

```py
>>> from statemachine.io import build_processor

>>> processor = build_processor(
...     '{"name": "M", "states": {"a": {"initial": true}}}', format="json"
... )
>>> sorted(processor.scs)
['M']

```
