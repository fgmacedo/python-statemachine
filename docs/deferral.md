(deferral)=

# Event deferral

```{versionadded} 3.3.0
```

```{seealso}
See {ref}`processing-model` for how events are queued and consumed, and {ref}`events`
for how they are declared and sent.
```

By default, an event that no active transition handles is dropped (or rejected, depending on
`allow_event_without_transition`). Sometimes the event is not wrong, only early: the
machine just is not ready for it yet. A state can **defer** such events. They are kept in a
queue instead of being discarded, and sent again as soon as the machine reaches a
configuration that no longer defers them.

This is the UML statechart notion of a *deferred event*.

## Deferring events in a state

Pass the ids of the events to the `defer` parameter of {ref}`State`:

```py
>>> from statemachine import State, StateChart

>>> class Council(StateChart):
...     gathering = State(initial=True, defer=["speak"])
...     deliberating = State()
...     decided = State(final=True)
...
...     convene = gathering.to(deliberating)
...     speak = deliberating.to(decided)

>>> sm = Council()
>>> sm.send("speak")
>>> sm.configuration_values
OrderedSet(['gathering'])

>>> sm.pending_deferred_event_ids
['speak']

```

The `speak` event arrived while the council was still `gathering`, which has no transition for it
and defers it. Nothing happened, but the event was remembered. Once the machine leaves
`gathering`, the queued event is put back at the end of the external queue and processed
like any other:

```py
>>> sm.send("convene")
>>> sm.configuration_values
OrderedSet(['decided'])

>>> sm.pending_deferred_event_ids
[]

```

Some details worth knowing:

- An event is only deferred when **no transition is enabled** for it. If the active state
  has a transition for the event, the transition runs as usual.
- Deferred events are replayed in the order they were sent (first in, first out), with the
  arguments they were sent with.
- An event that is replayed into a configuration that still defers it stays in the queue.
- Deferral takes precedence over `allow_event_without_transition`: a deferred event is queued
  whether the machine would otherwise ignore it or raise `TransitionNotAllowed`.
- The `defer` list does not need to name events declared in the class (see
  {ref}`validate_deferred_events <validating-deferred-events>`).
- A final state cannot defer events, since the machine does not process events after it
  terminates. The queue is cleared at that point.

## Deferral in compound and parallel states

A compound state defers events for all of its descendants. Use the `defer` class keyword:

```py
>>> class Journey(StateChart):
...     class mordor(State.Compound, defer=["rest"]):
...         gates = State(initial=True)
...         mount_doom = State()
...
...         climb = gates.to(mount_doom)
...
...     shire = State()
...     done = State(final=True)
...
...     return_home = mordor.to(shire)
...     rest = shire.to(done)

>>> sm = Journey()
>>> sm.send("rest")
>>> sm.send("climb")
>>> sm.pending_deferred_event_ids
['rest']

>>> sm.send("return_home")
>>> sm.configuration_values
OrderedSet(['done'])

```

A state defers an event if it lists the event or any of its ancestors does.
`State.deferred_events` holds what a state declares itself, and
`State.deferred_events_recursive` adds the ids declared by its ancestors.

In a parallel state there are several active atomic states at once, and the event is deferred
**only if all of them defer it**. If any region can still react to the event, it is processed
as usual and nothing is queued.

## Callbacks

Two optional callbacks follow the same pattern as `on_enter` and `on_exit`:

| Callback | When |
|---|---|
| `on_defer` | An event was added to the deferred queue. |
| `on_replay` | An event left the queue to be processed again. |

Both can be given inline to the state, or found by naming convention: `on_defer_event()` and
`on_replay_event()` for every state, `on_defer_<state_id>()` and `on_replay_<state_id>()` for a
specific one.

```py
>>> class Messenger(StateChart):
...     riding = State(initial=True, defer=["deliver"])
...     arrived = State()
...     delivered = State(final=True)
...
...     arrive = riding.to(arrived)
...     deliver = arrived.to(delivered)
...
...     def on_defer_riding(self, event):
...         print(f"{event} has to wait")
...
...     def on_replay_event(self, event, state):
...         print(f"{event} is back while in {state.id}")

>>> sm = Messenger()
>>> sm.send("deliver")
deliver has to wait

>>> sm.send("arrive")
deliver is back while in arrived

```

The callbacks run once for each active state that declares them, and receive the usual
{ref}`dependency injection <dependency-injection>` arguments: `machine`, `model`, `event`,
`state` and `source` (the same state) and `target`, which is always `None`. Arguments passed
to `send()` are available too. With the async engine the callbacks can be coroutines.

## Inspecting the queue

The {ref}`StateChart` instance exposes the queue:

- `deferred_events`: a copy of the queue, as a list of `TriggerData`.
- `pending_deferred_event_ids`: the ids of the queued events, in order.
- `is_event_deferred(event_id)`: whether an event would be deferred in the current
  configuration.
- `clear_deferred_queue()`: discards the queued events without replaying them.

```py
>>> sm = Council()
>>> sm.is_event_deferred("speak")
True

>>> sm.send("speak")
>>> [str(trigger.event) for trigger in sm.deferred_events]
['speak']

>>> sm.clear_deferred_queue()
>>> sm.send("convene")
>>> sm.configuration_values
OrderedSet(['deliberating'])

```

The queue is runtime state: it is not part of the serialized machine, so a pickled or copied
machine starts with an empty queue.

(validating-deferred-events)=

## Validating deferred events

A typo in a `defer` list is silent by default, because the event might be sent by code that is
not declared in the class. Set `validate_deferred_events = True` to require every deferred id
to be a declared event:

```py
>>> from statemachine.exceptions import InvalidDefinition

>>> try:
...     class Lookout(StateChart):
...         validate_deferred_events = True
...         watching = State(initial=True, defer=["relieved"])
...         relieved = State(final=True)
...         relieve = watching.to(relieved)
... except InvalidDefinition as e:
...     print(e)
State 'watching' defers unknown event(s): ['relieved']. Declared events are: ['relieve']

```
