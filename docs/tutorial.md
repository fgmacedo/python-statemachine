
# Tutorial

This tutorial walks you through python-statemachine from your first flat state
machine all the way to full statecharts — compound states, parallel regions,
history, and async. Each section builds on the previous one using the same
domain: **a coffee shop order system**.

By the end you will be comfortable defining states, transitions, guards,
actions, and listeners, and you will see how the same declarative API scales
from a five-state FSM to a production-grade statechart — no new concepts
required.


## Your first state machine

A coffee order goes through a few stages: the customer places it, the barista
prepares it, and the customer picks it up.

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     # Define the states
...     pending = State(initial=True)
...     preparing = State()
...     ready = State()
...     picked_up = State(final=True)
...
...     # Define events — each one groups one or more transitions
...     start = pending.to(preparing)
...     finish = preparing.to(ready)
...     pick_up = ready.to(picked_up)

```

That's it — states are class attributes, transitions are built with
`state.to(target)`, and events are the names you assign them to.

Create an instance and start sending events:

```py
>>> order = CoffeeOrder()
>>> order.pending.is_active
True

>>> order.send("start")
>>> order.preparing.is_active
True

>>> order.send("finish")
>>> order.send("pick_up")
>>> order.picked_up.is_active
True

```

You can also call events as methods — `order.start()` is equivalent to
`order.send("start")`:

```py
>>> order = CoffeeOrder()
>>> order.start()
>>> order.preparing.is_active
True

```

```{tip}
Use `sm.send("event_name")` when the event name is dynamic (e.g., comes from
user input or a message queue). Use `sm.event_name()` when writing
application code where the event is known at development time.
```


## Adding behavior with actions

A state machine without side effects is just a diagram. Actions let you
attach behavior to state entries, exits, and transitions.

Define actions by naming convention — the library discovers them
automatically:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State()
...     picked_up = State(final=True)
...
...     start = pending.to(preparing)
...     finish = preparing.to(ready)
...     pick_up = ready.to(picked_up)
...
...     # Called when entering the "preparing" state
...     def on_enter_preparing(self):
...         print("Barista starts making the drink.")
...
...     # Called when the "finish" event fires
...     def on_finish(self):
...         print("Drink is ready!")
...
...     # Called when entering the "picked_up" state
...     def on_enter_picked_up(self):
...         print("Customer picked up the order. Enjoy!")

>>> order = CoffeeOrder()
>>> order.send("start")
Barista starts making the drink.

>>> order.send("finish")
Drink is ready!

>>> order.send("pick_up")
Customer picked up the order. Enjoy!

```

The naming conventions are:

| Pattern                   | When it runs                          |
|---------------------------|---------------------------------------|
| `on_enter_<state>()`      | Every time `<state>` is entered       |
| `on_exit_<state>()`       | Every time `<state>` is exited        |
| `before_<event>()`        | Before any transition for `<event>`   |
| `on_<event>()`            | During the transition for `<event>`   |
| `after_<event>()`         | After the transition for `<event>`    |

```{seealso}
The full list of action callbacks and their execution order is in
[](actions.md).
```


### Dependency injection in callbacks

Callbacks don't need to accept a fixed signature. Declare only the
parameters you need, and the library injects them automatically:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State()
...     picked_up = State(final=True)
...
...     start = pending.to(preparing)
...     finish = preparing.to(ready)
...     pick_up = ready.to(picked_up)
...
...     def on_enter_preparing(self, source: State, target: State):
...         print(f"{source.id} → {target.id}")
...
...     def on_finish(self):
...         print("Done!")

>>> order = CoffeeOrder()
>>> order.send("start")
pending → preparing

>>> order.send("finish")
Done!

```

`on_enter_preparing` asks for `source` and `target` — it gets them.
`on_finish` asks for nothing extra — that's fine too.

Available parameters include `event`, `source`, `target`, `state`, and any
keyword arguments you pass to `send()`:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State(final=True)
...
...     start = pending.to(preparing)
...     finish = preparing.to(ready)
...
...     def on_start(self, drink: str = "coffee"):
...         print(f"Making a {drink}.")

>>> order = CoffeeOrder()
>>> order.send("start", drink="cappuccino")
Making a cappuccino.

```


## Guards: conditional transitions

Not every transition should always be allowed. Guards are conditions that
must be satisfied for a transition to fire.

A coffee order shouldn't move to `preparing` unless it has been paid for:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State()
...     picked_up = State(final=True)
...
...     # Two transitions on the same event — checked in declaration order.
...     # The first whose guard passes wins.
...     start = (
...         pending.to(preparing, cond="is_paid")
...         | pending.to(pending)  # fallback: stay in pending
...     )
...     finish = preparing.to(ready)
...     pick_up = ready.to(picked_up)
...
...     paid: bool = False
...
...     def is_paid(self):
...         return self.paid

>>> order = CoffeeOrder()

>>> order.send("start")  # not paid — stays in pending
>>> order.pending.is_active
True

>>> order.paid = True
>>> order.send("start")  # paid — moves to preparing
>>> order.preparing.is_active
True

```

Guards receive the same dependency injection as actions — you can
accept `event`, `source`, `target`, and any extra keyword arguments:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State(final=True)
...
...     start = (
...         pending.to(preparing, cond="is_paid")
...         | pending.to(pending)
...     )
...
...     def is_paid(self, amount: float = 0):
...         return amount >= 5.0

>>> order = CoffeeOrder()

>>> order.send("start", amount=3.0)
>>> order.pending.is_active
True

>>> order.send("start", amount=5.0)
>>> order.preparing.is_active
True

```

```{seealso}
See [](guards.md) for `unless=`, validators, boolean expressions
in condition strings, and evaluation order details.
```


## Observing from outside with listeners

Listeners let external objects react to state changes without touching the
state machine definition. Any object with methods matching the callback
naming conventions works as a listener.

The preferred way is to declare listeners at the class level — they are
automatically attached to every instance:

```py
>>> from statemachine import StateChart, State

>>> class NotificationService:
...     def on_enter_state(self, target: State):
...         print(f"[notify] Order is now: {target.id}")

>>> class CoffeeOrder(StateChart):
...     listeners = [NotificationService]
...
...     pending = State(initial=True)
...     preparing = State()
...     ready = State(final=True)
...
...     start = pending.to(preparing)
...     finish = preparing.to(ready)

>>> order = CoffeeOrder()
[notify] Order is now: pending

>>> order.send("start")
[notify] Order is now: preparing

>>> order.send("finish")
[notify] Order is now: ready

```

When the `listeners` list contains a **class** (like `NotificationService`
above), it acts as a factory — a fresh instance is created for each state
machine. Pass an already-built **instance** instead if you want a shared,
stateless listener (e.g., a global logger).

You can also add listeners at runtime, either via the constructor or on an
already running machine:

```py
>>> class AuditLog:
...     def after_transition(self, source: State, target: State, event: str):
...         print(f"[audit] {source.id} →({event})→ {target.id}")

>>> order = CoffeeOrder()
[notify] Order is now: pending

>>> _ = order.add_listener(AuditLog())

>>> order.send("start")
[notify] Order is now: preparing
[audit] pending →(start)→ preparing

```

The machine knows nothing about the listener, and the listener knows
nothing about the machine's internals — only the callback protocol.

```{seealso}
See [](listeners.md) for class-level listener configuration, `functools.partial`
factories, and the full list of listener callbacks.
```


## Generating diagrams

Visualize any state machine as a diagram:

```{statemachine-diagram} tests.machines.tutorial_coffee_order.CoffeeOrder
:alt: CoffeeOrder diagram
```

Generate diagrams programmatically with `_graph()`:

```python
order = CoffeeOrder()
order._graph().write_png("order.png")
```

Or from the command line:

```bash
python -m statemachine.contrib.diagram my_module.CoffeeOrder order.png
```

### Text representations with `format()`

You can also get text representations of any state machine using Python's built-in
`format()` or f-strings — no Graphviz needed:

```py
>>> from tests.machines.tutorial_coffee_order import CoffeeOrder

>>> print(f"{CoffeeOrder:md}")
| State     | Event   | Guard | Target    |
| --------- | ------- | ----- | --------- |
| Pending   | Start   |       | Preparing |
| Preparing | Finish  |       | Ready     |
| Ready     | Pick up |       | Picked up |

```

Supported formats include `mermaid`, `md` (markdown table), `rst`, `dot`, and `svg`.
Works on both classes and instances:

```py
>>> print(f"{CoffeeOrder:mermaid}")
stateDiagram-v2
    direction LR
    state "Pending" as pending
    state "Preparing" as preparing
    state "Ready" as ready
    state "Picked up" as picked_up
    [*] --> pending
    picked_up --> [*]
    pending --> preparing : Start
    preparing --> ready : Finish
    ready --> picked_up : Pick up
<BLANKLINE>

```

```{tip}
Graphviz diagram generation requires [Graphviz](https://graphviz.org/) (`dot` command)
and the `diagrams` extra:

    pip install python-statemachine[diagrams]

Text formats (`md`, `rst`, `mermaid`) work without any extra dependencies.
```

```{seealso}
See [](diagram.md) for all formats, highlighting active states, auto-expanding
docstrings, Jupyter integration, Sphinx directive, and the `quickchart_write_svg`
alternative that doesn't require Graphviz.
```


## Scaling up with statecharts

So far our coffee order has been a flat sequence of states. Real systems
are rarely that simple — what happens when preparing a drink involves
multiple steps? What if the order includes both a drink *and* a snack
prepared in parallel?

This is where python-statemachine shines: you scale from a flat FSM to a
full statechart using the **exact same API**. No new base class, no
configuration flags — just nest your states.


### Compound states: breaking complexity into levels

Preparing a drink isn't a single step. Let's model it as a compound state
with sub-steps — grinding, brewing, and serving:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...
...     class preparing(State.Compound):
...         """Drink preparation with internal steps."""
...         grinding = State(initial=True)
...         brewing = State()
...         serving = State(final=True)
...
...         grind = grinding.to(brewing)
...         brew = brewing.to(serving)
...
...     picked_up = State(final=True)
...
...     start = pending.to(preparing)
...     done_state_preparing = preparing.to(picked_up)

>>> order = CoffeeOrder()
>>> order.send("start")
>>> set(order.configuration_values) == {"preparing", "grinding"}
True

>>> order.send("grind")
>>> "brewing" in order.configuration_values
True

>>> order.send("brew")
>>> order.picked_up.is_active
True

```

Entering `preparing` activates both the compound parent and its initial
child (`grinding`). When `serving` — a final child — is reached,
`done.state.preparing` fires automatically and transitions to `picked_up`.

Notice how nothing changed about the outer API. You still `send("start")`
to begin — the compound structure is an internal detail.


### Parallel states: concurrent regions

Now let's say the order includes both a drink and a snack, prepared at the
same time by different stations:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...
...     class preparing(State.Parallel):
...         class drink(State.Compound):
...             brewing = State(initial=True)
...             drink_done = State(final=True)
...             brew = brewing.to(drink_done)
...         class snack(State.Compound):
...             heating = State(initial=True)
...             snack_done = State(final=True)
...             heat = heating.to(snack_done)
...
...     picked_up = State(final=True)
...
...     start = pending.to(preparing)
...     done_state_preparing = preparing.to(picked_up)

>>> order = CoffeeOrder()
>>> order.send("start")
>>> "brewing" in order.configuration_values and "heating" in order.configuration_values
True

>>> order.send("brew")  # drink done, snack still heating
>>> "drink_done" in order.configuration_values and "heating" in order.configuration_values
True

>>> order.is_terminated  # drink region finished, but snack hasn't
False

>>> order.send("heat")  # both done — auto-transitions to picked_up
>>> order.picked_up.is_active
True

>>> order.is_terminated
True

```

`State.Parallel` activates all child regions at once. Each region
processes events independently. The machine only transitions out when
**every** region reaches a final state.



### Checking completion with `is_terminated`

In a flat state machine, checking whether you've reached a specific
final state is enough. But with compound and parallel states, completion
depends on the structure — all regions of a parallel must finish, nested
compounds must reach their own final children, and so on. The
`is_terminated` property handles this for you: it returns `True` only
when the entire machine has completed its work, regardless of how deeply
nested the structure is. Use it instead of checking individual states.

A common pattern is to consume events from a queue or stream, feeding
them to the machine until it terminates:

```py
>>> from collections import deque

>>> order = CoffeeOrder()
>>> queue = deque(["start", "brew", "heat"])

>>> while not order.is_terminated and queue:
...     order.send(queue.popleft())

>>> order.is_terminated
True

```

This decouples event production from consumption — the queue could come
from a message broker, a file, user input, or any other source.


### History states: remember where you left off

What if the barista needs to pause preparation (e.g., to handle a rush)
and resume later? A history state remembers which child was active when a
compound was exited:

```py
>>> from statemachine import HistoryState, StateChart, State

>>> class CoffeeOrder(StateChart):
...     class preparing(State.Compound):
...         grinding = State(initial=True)
...         brewing = State()
...         done = State(final=True)
...         h = HistoryState()
...
...         grind = grinding.to(brewing)
...         brew = brewing.to(done)
...
...     paused = State()
...     finished = State(final=True)
...
...     pause = preparing.to(paused)
...     resume = paused.to(preparing.h)  # ← return via history
...     done_state_preparing = preparing.to(finished)

>>> order = CoffeeOrder()
>>> order.send("grind")     # now in "brewing"
>>> "brewing" in order.configuration_values
True

>>> order.send("pause")     # leave preparing
>>> order.send("resume")    # history restores "brewing", not "grinding"
>>> "brewing" in order.configuration_values
True

>>> order.send("brew")      # finish preparation
>>> order.finished.is_active
True

```

Use `HistoryState(type="deep")` for deep history that remembers the exact
leaf state across nested compounds.


### Eventless transitions: react automatically

Eventless transitions fire without an explicit event — they trigger
automatically when their guard condition is met:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State()
...     picked_up = State(final=True)
...
...     # Eventless: fires automatically when the guard is satisfied
...     pending.to(preparing, cond="is_paid")
...     ready.to(picked_up, cond="was_picked_up")
...
...     finish = preparing.to(ready)
...
...     # A no-op event to re-enter the processing loop
...     check = (
...         pending.to.itself(internal=True)
...         | ready.to.itself(internal=True)
...     )
...
...     paid: bool = False
...     picked: bool = False
...
...     def is_paid(self):
...         return self.paid
...     def was_picked_up(self):
...         return self.picked

>>> order = CoffeeOrder()
>>> order.paid = True
>>> order.send("check")  # triggers the eventless transition
>>> order.preparing.is_active
True

>>> order.send("finish")
>>> order.picked = True
>>> order.send("check")
>>> order.picked_up.is_active
True

```

Eventless transitions are evaluated after every macrostep. Combined with
guards, they let the machine react to changes in its own data without
requiring the outside world to name every event.


### Error handling as events

With `StateChart`, runtime exceptions in callbacks don't crash the
machine — they become `error.execution` events that you can handle with
regular transitions:

```py
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     preparing = State(initial=True)
...     out_of_stock = State(final=True)
...
...     make_drink = preparing.to(preparing, on="do_make_drink")
...     error_execution = preparing.to(out_of_stock)
...
...     def do_make_drink(self):
...         raise RuntimeError("Out of oat milk!")
...
...     def on_enter_out_of_stock(self, error=None):
...         if error:
...             print(f"Problem: {error}")

>>> order = CoffeeOrder()
>>> order.send("make_drink")
Problem: Out of oat milk!
>>> order.out_of_stock.is_active
True

```

The exception is caught, dispatched as an internal `error.execution`
event, and handled by the `error_execution` transition — no try/except
needed in your application code.

```{seealso}
See [](error_handling.md) for the full `error.execution` lifecycle,
block-level error catching, and the cleanup/finalize pattern.
```


### Async: same API, no changes needed

Every example above works with async callbacks too. Just use `async def`
and the engine switches automatically:

```py
>>> import asyncio
>>> from statemachine import StateChart, State

>>> class CoffeeOrder(StateChart):
...     pending = State(initial=True)
...     preparing = State()
...     ready = State(final=True)
...
...     start = pending.to(preparing)
...     finish = preparing.to(ready)
...
...     async def on_start(self, drink: str = "coffee"):
...         return f"Started making {drink}"
...
...     async def on_finish(self):
...         return "Drink is ready!"

>>> async def main():
...     order = CoffeeOrder()
...     result = await order.send("start", drink="latte")
...     print(result)
...     result = await order.send("finish")
...     print(result)

>>> asyncio.run(main())
Started making latte
Drink is ready!

```

No special async base class. No configuration. The same `StateChart`
class, the same `send()` method, the same naming conventions — just
`async def` and `await`.

```{seealso}
See [](async.md) for the sync vs. async engine selection table,
initial state activation in async contexts, and concurrent event sending.
```


## Next steps

You now have a solid foundation. Here are the most useful pages to
explore next:

- **[States](states.md)** — final states, compound states, parallel states, history, `DoneData`
- **[Transitions](transitions.md)** — self-transitions, internal transitions, cross-boundary, delayed events
- **[Actions](actions.md)** — the full callback execution order, `prepare_event()`
- **[Guards](guards.md)** — `unless=`, validators, boolean expressions, `In()` for cross-region checks
- **[Listeners](listeners.md)** — the observer pattern in depth
- **[Error handling](error_handling.md)** — `error.execution` events, block-level catching, cleanup patterns
- **[Processing model](processing_model.md)** — `send()` vs `raise_()`, microstep/macrostep, run-to-completion
- **[Behaviour](behaviour.md)** — `StateChart` vs `StateMachine`, behavioral flags, and migration guide
- **[Django integration](integrations.md)** — auto-discovery, `MachineMixin` with Django models
- **[Diagrams](diagram.md)** — CLI generation, Jupyter, SVG, DPI settings
- **[API reference](api.md)** — full class and method reference
