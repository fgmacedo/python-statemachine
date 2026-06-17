# The declarative format

JSON and YAML are two serializations of a **single declarative format** built from the
library's own vocabulary. Authoring is about *what you express*, not *which serialization*:
the same document in either format compiles to the same state machine. Pick YAML for
readability, or JSON when a tool emits or consumes it. (SCXML, the W3C XML standard, loads
the same way and is covered at the [end of this page](#scxml).)

A document has an optional top-level envelope (`name`, `description`, `datamodel`) and a
`states` mapping keyed by state id. Here is the same toggle written both ways, proving the
result is identical:

```py
>>> from statemachine.io import load

>>> yaml_doc = """
... states:
...   lit:
...     initial: true
...     transitions:
...       - {event: toggle, target: dark}
...   dark:
...     transitions:
...       - {event: toggle, target: lit}
... """
>>> json_doc = '''
... {"states": {
...     "lit":  {"initial": true, "transitions": [{"event": "toggle", "target": "dark"}]},
...     "dark": {"transitions": [{"event": "toggle", "target": "lit"}]}
... }}
... '''
>>> def first_target(doc, fmt):
...     sm = load(doc, format=fmt, validate=True)()
...     _ = sm.send("toggle")
...     return sorted(sm.configuration_values)
>>> first_target(yaml_doc, "yaml") == first_target(json_doc, "json") == ["dark"]
True

```

The rest of this page uses YAML for readability; every example is equally expressible in
JSON. Each section links to the core guide for the concept, and shows how to write it in a
document. The examples pass `validate=True` so each one is also checked against the
[JSON Schema](json_schema.md) as it runs; the flag is optional and needs the `[validation]`
extra.

## States

A state is a key under `states`. Mark one as `initial`; mark accepting states as `final`.
Nest a `states` mapping for a compound state, set `parallel: true` for orthogonal regions,
and add a `history` mapping for history pseudo-states. The concepts and their semantics are
covered in [](../states.md); here is the declarative shape:

```py
>>> sc = load(
...     """
...     states:
...       work:
...         initial: true
...         states:
...           writing:
...             initial: true
...             transitions:
...               - {event: submit, target: reviewing}
...           reviewing:
...             transitions:
...               - {event: approve, target: shipped}
...       shipped:
...         final: true
...     """,
...     format="yaml",
...     validate=True,
... )
>>> sm = sc()
>>> sorted(sm.configuration_values)
['work', 'writing']
>>> _ = sm.send("submit")
>>> _ = sm.send("approve")
>>> sorted(sm.configuration_values)
['shipped']

```

## Transitions

Each state has a single `transitions` list. Every item is self-describing and carries its
own `event`, `target`, `cond`/`unless` guards and `on` actions. Omitting `event` makes the
transition **eventless** (it fires automatically whenever its guard holds); omitting
`target` makes it a self-transition that only runs its actions. See [](../transitions.md).

```py
>>> sc = load(
...     """
...     datamodel:
...       - {id: count, expr: "0"}
...     states:
...       counting:
...         initial: true
...         transitions:
...           - event: tick
...             target: counting
...             on:
...               - assign: {location: count, expr: "count + 1"}
...           - target: done          # eventless: fires when count reaches 3
...             cond: "count >= 3"
...       done:
...         final: true
...     """,
...     format="yaml",
...     validate=True,
... )
>>> sm = sc()
>>> for _ in range(3):
...     _ = sm.send("tick")
>>> sorted(sm.configuration_values)
['done']

```

```{note}
**The `on` key in YAML.** Loaded through {func}`~statemachine.io.load`, a transition's
`on` action key is safe: the library's YAML reader keeps `on` (and `off`/`yes`/`no`) as
plain strings. But standard YAML 1.1 tooling, PyYAML's `safe_load`, `yq`, generic YAML→JSON
converters, coerces a bare `on:` into the boolean `true`. If another tool will read or
rewrite your document, quote the key (`"on":`) or author it in JSON, where the key is always
a string.
```

## Guards

`cond` and `unless` are *expressions* ([](../guards.md)), not method names. They are
evaluated against the runtime context: the datamodel, the bound model, the system variables,
and the **data carried by the event** — `_event.data.<name>`, populated from the keyword
arguments passed to `send`. So a routing decision depends on what arrives at runtime, not on
a value frozen in the document:

```py
>>> sc = load(
...     """
...     states:
...       inbox:
...         initial: true
...         transitions:
...           - {event: route, target: urgent, cond: "_event.data.priority >= 9"}
...           - {event: route, target: normal, cond: "_event.data.priority >= 5"}
...           - {event: route, target: low}
...       urgent: {final: true}
...       normal: {final: true}
...       low: {final: true}
...     """,
...     format="yaml",
...     validate=True,
... )
>>> sm = sc()
>>> _ = sm.send("route", priority=7)
>>> sorted(sm.configuration_values)
['normal']

```

Under the secure default, guards support comparisons, boolean algebra and the `In(state_id)`
predicate, so this routing logic needs no `trusted=True`. What the restricted evaluator does
and does not allow is detailed in [](security.md).

A guard follows the [Python guard dialect](../guards.md#condition-expressions): alongside
boolean and comparison operators over the event payload, datamodel variables and system
variables, a bare name on the model is resolved exactly as in a class-defined guard, a
property or attribute is *read* and a **method** is *called* (with dependency injection). So
`cond: "approves"` invokes the method, receiving the event's keyword arguments:

```py
>>> sc = load(
...     """
...     states:
...       review:
...         initial: true
...         transitions:
...           - {event: decide, target: approved, cond: "approves"}
...           - {event: decide, target: rejected}
...       approved: {final: true}
...       rejected: {final: true}
...     """,
...     format="yaml",
...     validate=True,
... )
>>> class Reviewer:
...     def approves(self, amount=0, **kwargs):
...         return amount <= 1000
>>> sm = sc(model=Reviewer())
>>> _ = sm.send("decide", amount=500)
>>> sorted(sm.configuration_values)
['approved']

```

`cond` and `unless` also accept a list; the transition is taken only when every entry holds.

## Actions

Five positions carry behaviour: a state's `enter` and `exit`, and a transition's `before`,
`on` and `after`. They are uniform, each takes a single item or a list, and each item is
either a **callback reference** (a method name on the model) or a **structured action**:

| Position | Callback reference | Structured action | `script` |
|---|:--:|:--:|:--:|
| state `enter` / `exit` | yes | yes | trusted only |
| transition `on` | yes | yes | trusted only |
| transition `before` / `after` | yes | yes | trusted only |

`before` and `after` are native-only (SCXML has no equivalent lifecycle slot). Guards
(`cond`/`unless`) are not action positions, they are expressions, covered under
[Guards](#guards).

The structured action vocabulary, evaluated by the secure evaluator:

| Action | Shape |
|---|---|
| `assign` | `{assign: {location: x, expr: "..."}}` |
| `raise` | `{raise: event_name}` |
| `log` | `{log: {label: L, expr: "..."}}` or `{log: "expr"}` |
| `if` | `{if: {cond: "...", then: [...], elif: [{cond, then}], else: [...]}}` |
| `foreach` | `{foreach: {array: "...", item: i, index: idx, do: [...]}}` |
| `send` | `{send: {event: e, target: "...", delay: "...", params: [...]}}` |
| `cancel` | `{cancel: {sendid: "..."}}` |
| `script` | `{script: "..."}` (rejected unless `trusted=True`) |

## Callback references

A bare string in any of the five action positions (a state's `enter`/`exit`, or a
transition's `before`/`on`/`after`) is a **callback reference**: the name of a method on the
bound model. This is how a declarative document drives your own Python while staying safe to
load: the runtime *calls* the method with the usual dependency injection
([](../actions.md#dependency-injection)), so the body is arbitrary Python even in secure mode.

The name need *not* follow the `on_<event>`/`on_enter_<state>` auto-binding convention. A
reference binds *any* method explicitly, which is the point: it integrates code that the
convention would not pick up.

```py
>>> sc = load(
...     """
...     states:
...       cart:
...         initial: true
...         transitions:
...           - event: checkout
...             target: paid
...             on: charge_card
...       paid:
...         enter: send_receipt
...         final: true
...     """,
...     format="yaml",
...     validate=True,
... )

>>> class Shop:
...     def __init__(self):
...         self.balance = 100
...         self.receipts = []
...     def charge_card(self, amount):
...         self.balance -= amount
...     def send_receipt(self):
...         self.receipts.append(self.balance)

>>> shop = Shop()
>>> sm = sc(model=shop)
>>> _ = sm.send("checkout", amount=30)
>>> shop.balance, shop.receipts
(70, [70])

```

`charge_card` and `send_receipt` are not convention names, yet the document calls them at
the right moments and they run arbitrary Python (here reading the event's `amount`).

### The `before` / `on` / `after` lifecycle

A transition runs three callback groups around the state change, in order: `before` (the
guards have passed, the machine has not moved yet), `on` (during the transition), and
`after` (the configuration has settled). See [](../actions.md#transition-actions). The
native format exposes all three as transition keys, so every transition callback the library
supports is expressible in a document, not just `on`:

```py
>>> sc = load(
...     """
...     states:
...       editing:
...         initial: true
...         transitions:
...           - event: save
...             target: saved
...             before: validate
...             on: persist
...             after: notify
...       saved:
...         final: true
...     """,
...     format="yaml",
...     validate=True,
... )

>>> class Doc:
...     def __init__(self):
...         self.steps = []
...     def validate(self):
...         self.steps.append("validate")
...     def persist(self):
...         self.steps.append("persist")
...     def notify(self):
...         self.steps.append("notify")

>>> doc = Doc()
>>> sm = sc(model=doc)
>>> _ = sm.send("save")
>>> doc.steps
['validate', 'persist', 'notify']

```

Here all three slots hold callback references, but each accepts the full vocabulary from the
[Actions](#actions) matrix, structured actions and `script` included, just like `on`.

## Trusted mode

Pass `trusted=True` to evaluate guards and expressions as **full Python** — method calls,
builtins, comprehensions — and to enable `script`, a block of Python statements that reads
and writes the model's variables. Only do this for documents you control, since it executes
arbitrary code ([](security.md)):

```py
>>> sc = load(
...     """
...     datamodel:
...       - {id: cart, expr: "[10, 25, 5]"}
...       - {id: total, expr: "0"}
...       - {id: tier, expr: "''"}
...     states:
...       pricing:
...         initial: true
...         enter:
...           - script: |
...               total = sum(cart)
...               tier = 'gold' if total >= 40 else 'silver'
...         transitions:
...           - {target: vip, cond: "tier == 'gold' and len(cart) >= 3"}
...           - {target: standard}
...       vip:
...         final: true
...       standard:
...         final: true
...     """,
...     format="yaml",
...     trusted=True,
...     validate=True,
... )
>>> sm = sc()
>>> sm.model.total, sm.model.tier
(40, 'gold')
>>> sorted(sm.configuration_values)
['vip']

```

The `script` block uses `sum(...)`; the eventless guard uses `len(...)`. Both are builtins
the restricted evaluator rejects, so this document only runs because of `trusted=True`.

## Datamodel

`datamodel` declares initial variables on the bound model, either as a list of `{id, expr}`
items or as a mapping shorthand. Each `expr` is evaluated once at construction:

```py
>>> sc = load(
...     """
...     datamodel:
...       x: "10"
...       label: "'ready'"
...     states:
...       a: {initial: true}
...     """,
...     format="yaml",
...     validate=True,
... )
>>> sm = sc()
>>> sm.model.x, sm.model.label
(10, 'ready')

```

## System variables

The execution model's system variables — `_event`, `_sessionid`, `_name`, `_ioprocessors` —
are available to guards and actions in **every** format. So a document can read the current
event the same way it would in SCXML:

```py
>>> sc = load(
...     """
...     states:
...       start:
...         initial: true
...         transitions:
...           - event: ping
...             target: pong
...             cond: "_event.name == 'ping'"
...       pong:
...         final: true
...     """,
...     format="yaml",
...     validate=True,
... )
>>> sm = sc()
>>> _ = sm.send("ping")
>>> sorted(sm.configuration_values)
['pong']

```

## Invoke

A state can `invoke` a child statechart ([](../invoke.md)). The child may be inline
`content` (a nested statechart) or referenced by `src` (a file in the same format);
`params`/`namelist` pass data in, `finalize` runs on child events, and the child can target
the parent with `send` to `#_parent`:

```yaml
states:
  waiting:
    initial: true
    invoke:
      - content:
          states:
            running:
              initial: true
              enter:
                - send: {event: done, target: "#_parent"}
    transitions:
      - {event: done, target: finished}
  finished:
    final: true
```

Invoke spawns a child machine that runs concurrently, so the parent reaches `finished` only
once the child signals back. Because that resolution is not synchronous, the example above
is shown for structure rather than as a doctest.

## SCXML

[SCXML](https://www.w3.org/TR/scxml/) (State Chart XML) is the W3C standard this library's
execution model follows. It is a different serialization of the same model, so you load it
through the same {func}`~statemachine.io.load` facade and everything on this page applies:
the run-to-completion semantics, the action vocabulary, guards, the datamodel, system
variables and `invoke`.

```py
>>> sc = load(
...     '''
...     <scxml xmlns="http://www.w3.org/2005/07/scxml" initial="s1" name="Demo">
...       <state id="s1">
...         <transition event="go" target="s2"/>
...       </state>
...       <final id="s2"/>
...     </scxml>
...     ''',
...     format="scxml",
... )
>>> sm = sc()
>>> _ = sm.send("go")
>>> sorted(sm.configuration_values)
['s2']

```

SCXML is executable content, so the same security rules apply: expressions are evaluated by
the restricted evaluator and `<script>` is rejected unless you pass `trusted=True` (see
[](security.md)). Documents that declare or `<invoke>` several machines are reachable through
{func}`~statemachine.io.build_processor`, exactly as shown in [](index.md#multiple-machines-in-one-document).
