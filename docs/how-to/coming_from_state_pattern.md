(coming-from-state-pattern)=

# Coming from the State Pattern

This guide is for developers familiar with the classic **State Pattern** from the
Gang of Four book (*Design Patterns: Elements of Reusable Object-Oriented Software*).
It walks through a typical State Pattern implementation, discusses its trade-offs,
and shows how to express the same behavior declaratively with python-statemachine.

## The classic State Pattern

The GoF State Pattern models an object whose behavior changes based on its internal
state. The standard recipe has three ingredients:

1. A **Context** class that delegates behavior to a state object.
2. An **abstract State** base class (or protocol) defining the interface.
3. **Concrete State** classes implementing state-specific behavior.

Here is a complete example — an order workflow with four states
(draft, confirmed, shipped, delivered) and a guard condition
(orders can only be confirmed if they have at least one item):

```python
from abc import ABC, abstractmethod


class OrderState(ABC):
    """Abstract base for all order states."""

    @abstractmethod
    def confirm(self, order):
        ...

    @abstractmethod
    def ship(self, order):
        ...

    @abstractmethod
    def deliver(self, order):
        ...


class DraftState(OrderState):
    def confirm(self, order):
        if order.item_count <= 0:
            raise ValueError("Cannot confirm an empty order")
        order._state = ConfirmedState()
        print("Order confirmed")

    def ship(self, order):
        raise RuntimeError("Cannot ship a draft order")

    def deliver(self, order):
        raise RuntimeError("Cannot deliver a draft order")


class ConfirmedState(OrderState):
    def confirm(self, order):
        raise RuntimeError("Order already confirmed")

    def ship(self, order):
        order._state = ShippedState()
        print("Order shipped")

    def deliver(self, order):
        raise RuntimeError("Cannot deliver before shipping")


class ShippedState(OrderState):
    def confirm(self, order):
        raise RuntimeError("Cannot confirm a shipped order")

    def ship(self, order):
        raise RuntimeError("Order already shipped")

    def deliver(self, order):
        order._state = DeliveredState()
        print("Order delivered")


class DeliveredState(OrderState):
    def confirm(self, order):
        raise RuntimeError("Order already delivered")

    def ship(self, order):
        raise RuntimeError("Order already delivered")

    def deliver(self, order):
        raise RuntimeError("Order already delivered")


class Order:
    def __init__(self, item_count=0):
        self._state = DraftState()
        self.item_count = item_count

    def confirm(self):
        self._state.confirm(self)

    def ship(self):
        self._state.ship(self)

    def deliver(self):
        self._state.deliver(self)
```

This works — but notice how much code it takes for just four states and three events.


## Pros and cons of the classic pattern

**Pros:**

- Encapsulates state-specific behavior in dedicated classes, eliminating large
  `if/elif` chains.
- Follows the Open/Closed Principle for adding new states — you create a new class
  without modifying existing ones.
- Each state class is independently testable.

**Cons:**

- **Class explosion** — every state requires a full class, even if most methods just
  raise "invalid operation" errors. The example above has 4 state classes and 12
  method implementations, 9 of which only raise exceptions.
- **Transitions are scattered** — to understand the full workflow you must read every
  concrete state class. There is no single place showing all transitions at a glance.
- **No structural validation** — orphaned states, unreachable states, or missing
  transitions are only discovered at runtime.
- **Guards are manual** — conditions like "only confirm if items > 0" are embedded in
  method bodies, mixed with transition logic.
- **No diagrams** — visualizing the state machine requires manual drawing.
- **No async support** — adding async behavior requires rewriting the entire interface.
- **Signature duplication** — every state class must implement every method, even the
  ones that are not valid for that state.


## Porting to python-statemachine

The same order workflow expressed declaratively:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.exceptions import TransitionNotAllowed

>>> class OrderMachine(StateChart):
...     allow_event_without_transition = False
...
...     # States
...     draft = State(initial=True)
...     confirmed = State()
...     shipped = State()
...     delivered = State(final=True)
...
...     # Transitions (the complete workflow at a glance)
...     confirm = draft.to(confirmed, cond="has_items")
...     ship = confirmed.to(shipped)
...     deliver = shipped.to(delivered)
...
...     item_count = 0
...
...     @property
...     def has_items(self):
...         return self.item_count > 0

>>> sm = OrderMachine()
>>> sm.item_count = 3
>>> sm.send("confirm")
>>> sm.confirmed.is_active
True

>>> sm.send("ship")
>>> sm.shipped.is_active
True

>>> sm.send("deliver")
>>> sm.delivered.is_active
True

```

That is the **entire** state machine — states, transitions, and the guard condition,
all in one place. Setting `allow_event_without_transition = False` gives strict
behavior equivalent to the GoF pattern — invalid events raise
`TransitionNotAllowed`:

```py
>>> sm = OrderMachine()
>>> sm.item_count = 3

>>> try:
...     sm.send("ship")  # can't ship from draft
... except TransitionNotAllowed:
...     print("Blocked: can't ship from draft")
Blocked: can't ship from draft

```

Guards work the same way — when the condition is not met, the transition is
rejected:

```py
>>> sm = OrderMachine()

>>> try:
...     sm.send("confirm")  # item_count is 0
... except TransitionNotAllowed:
...     print("Cannot confirm an empty order")
Cannot confirm an empty order

```

### Going reactive

The strict mode above is a direct equivalent of the GoF pattern. But `StateChart`'s
default (`allow_event_without_transition = True`) follows the SCXML specification:
events that have no valid transition are **skipped**. This makes the
machine reactive — it only responds to events that are meaningful in its current
state, without requiring the caller to know which events are valid:

```py
>>> class ReactiveOrderMachine(StateChart):
...     draft = State(initial=True)
...     confirmed = State()
...     shipped = State()
...     delivered = State(final=True)
...
...     confirm = draft.to(confirmed, cond="has_items")
...     ship = confirmed.to(shipped)
...     deliver = shipped.to(delivered)
...
...     item_count = 0
...
...     @property
...     def has_items(self):
...         return self.item_count > 0

>>> sm = ReactiveOrderMachine()
>>> sm.item_count = 3

>>> sm.send("ship")       # no transition for "ship" from draft — skipped
>>> sm.draft.is_active    # still in draft
True

>>> sm.send("confirm")    # this one is valid
>>> sm.confirmed.is_active
True

```

This is particularly useful when the machine receives events from external sources
(message queues, UI frameworks, network protocols) where the sender doesn't track
the machine's current state. See {ref}`behaviour` for a comparison of all
class-level defaults.

### Adding callbacks

State-specific behavior (e.g., sending notifications) uses naming conventions
or inline declarations — no need to scatter logic across state classes:

```py
>>> from statemachine import State, StateChart

>>> class OrderWithCallbacks(StateChart):
...     draft = State(initial=True)
...     confirmed = State()
...     shipped = State()
...     delivered = State(final=True)
...
...     confirm = draft.to(confirmed, cond="has_items")
...     ship = confirmed.to(shipped)
...     deliver = shipped.to(delivered)
...
...     item_count = 0
...
...     def __init__(self, **kwargs):
...         self.log = []
...         super().__init__(**kwargs)
...
...     @property
...     def has_items(self):
...         return self.item_count > 0
...
...     def on_enter_confirmed(self):
...         self.log.append("confirmed")
...
...     def on_enter_shipped(self):
...         self.log.append("shipped")
...
...     def on_enter_delivered(self):
...         self.log.append("delivered")

>>> sm = OrderWithCallbacks()
>>> sm.item_count = 2
>>> sm.send("confirm")
>>> sm.send("ship")
>>> sm.send("deliver")
>>> sm.log
['confirmed', 'shipped', 'delivered']

```

### Structural validation catches design errors

Imagine a new requirement: orders can be cancelled from `draft` or `confirmed`.
With the GoF pattern, a developer adds a `CancelledState` class — but forgets to
wire the transitions in `DraftState` and `ConfirmedState`. The code compiles and
runs fine; the bug only surfaces when someone tries to cancel an order and
discovers there is no way to reach `CancelledState`. In a large codebase with
dozens of states, this kind of mistake can go unnoticed for a long time.

python-statemachine catches this at **class definition time**:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.exceptions import InvalidDefinition

>>> try:
...     class BrokenOrderMachine(StateChart):
...         draft = State(initial=True)
...         confirmed = State()
...         shipped = State()
...         delivered = State(final=True)
...         cancelled = State(final=True)  # added but never connected
...
...         confirm = draft.to(confirmed)
...         ship = confirmed.to(shipped)
...         deliver = shipped.to(delivered)
... except InvalidDefinition as e:
...     print(e)
There are unreachable states. ...Disconnected states: ['cancelled']

```

The fix is to declare the missing transitions — and now the full workflow is
visible in a single glance:

```py
>>> class FixedOrderMachine(StateChart):
...     draft = State(initial=True)
...     confirmed = State()
...     shipped = State()
...     delivered = State(final=True)
...     cancelled = State(final=True)
...
...     confirm = draft.to(confirmed)
...     ship = confirmed.to(shipped)
...     deliver = shipped.to(delivered)
...     cancel = draft.to(cancelled) | confirmed.to(cancelled)

>>> sm = FixedOrderMachine()
>>> sm.send("cancel")
>>> sm.cancelled.is_active
True

```


## Side-by-side comparison

| Concept | State Pattern (GoF) | python-statemachine |
|---|---|---|
| State definition | One class per state | `State()` class attribute |
| Transition | Method in source state class sets `_state` | `.to()` declaration |
| Guard / condition | `if` check inside method body | `cond=` / `unless=` parameter |
| Invalid transition | Manual `raise` in every method | `TransitionNotAllowed` or skipped ({ref}`configurable <behaviour>`) |
| All transitions | Scattered across state classes | Visible in the class body |
| Context / model | Separate `Order` class | `StateChart` itself (or `model=`) |
| Adding a new state | New class + update all interfaces | New `State()` attribute + transitions |
| Entry / exit actions | Manual in transition methods | `on_enter_<state>()` / `on_exit_<state>()` |
| Diagrams | Manual | Built-in `_graph()` |
| Validation | None (runtime errors only) | Definition-time structural checks |
| Async support | Rewrite entire interface | Auto-detected from `async def` |
| Dependency injection | Not available | Built-in via `SignatureAdapter` |


## What you gain

By moving from the State Pattern to python-statemachine, you get:

- **Declarative definition** — the entire workflow is visible in one class body.
- **Structural validation** — unreachable states, missing transitions, and unresolved
  callbacks are caught before the machine ever runs
  (see {ref}`validations`).
- **Automatic diagrams** — call `_graph()` on any instance to generate a Graphviz
  diagram (see {ref}`diagrams`).
- **Guards and conditions** — use `cond=`, `unless=`, or
  {ref}`expression strings <condition expressions>` instead of manual `if` checks.
- **Dependency injection** — callbacks receive only the parameters they declare
  (see {ref}`actions`).
- **Async support** — define `async def` callbacks and the engine auto-switches to
  async processing (see {ref}`async`).
- **Listeners** — attach cross-cutting concerns (logging, auditing) as separate
  objects without modifying the state machine
  (see {ref}`listeners`).
- **No class explosion** — four states and three events require one class with a few
  attributes, not four classes with twelve methods.
