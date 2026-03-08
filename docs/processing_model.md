(processing-model)=
(processing model)=

# Processing model

The engine processes events following the
[SCXML](https://www.w3.org/TR/scxml/#AlgorithmforSCXMLInterpretation)
**run-to-completion** (RTC) model: each event is fully processed — all
callbacks executed, all states entered/exited — before the next event
starts. This guarantees the system is always in a consistent state when
a new event arrives.

> **Run to completion** — SCXML adheres to a run to completion semantics
> in the sense that an external event can only be processed when the
> processing of the previous external event has completed, i.e. when all
> microsteps (involving all triggered transitions) have been completely
> taken.
>
> — [W3C SCXML Specification](https://www.w3.org/TR/scxml/#AlgorithmforSCXMLInterpretation)

```{seealso}
See {ref}`actions` for the callback execution order within each step,
{ref}`sending-events` for how to trigger events, and {ref}`behaviour`
for customizations that affect how the engine processes transitions.
```


(macrostep-microstep)=

## Macrosteps and microsteps

The processing loop is organized into two levels:

### Microstep

A **microstep** is the smallest unit of processing. It takes a set of
enabled transitions and walks them through a fixed sequence of
callback groups defined in the {ref}`execution order <actions>`:

1. **Prepare** — enrich event kwargs.
2. **Validators / Conditions** — check if the transition is allowed.
3. **Before** — run pre-transition callbacks.
4. **Exit** — leave source states (innermost first).
5. **On** — execute transition actions.
6. **Enter** — enter target states (outermost first).
7. **Invoke** — spawn background work.
8. **After** — run post-transition callbacks (always runs, even on error).

```{tip}
If an error occurs during steps 3–6 and `catch_errors_as_events` is enabled,
the error is caught at the **block level** — remaining actions in that block
are skipped, but the microstep continues. See
{ref}`error-execution` and the
{ref}`cleanup / finalize pattern <error-handling-cleanup-finalize>`.
```


### Macrostep

A **macrostep** is a complete processing cycle triggered by a single
external event. It consists of one or more microsteps and only ends when
the machine reaches a **stable configuration** — no eventless transitions
are enabled and the internal queue is empty.

Within a single macrostep, the engine repeats:

1. **Check eventless transitions** — transitions without an event that
   fire automatically when their guard conditions are met.
2. **Drain the internal queue** — events placed by `raise_()` are
   processed immediately, before any external events.
3. If neither step produced a transition, the macrostep is **done**.

After the macrostep completes, the engine picks the next event from the
**external queue** (placed by `send()`) and starts a new macrostep.


### Event queues

The engine maintains two separate FIFO queues:

| Queue | How to enqueue | When processed |
|---|---|---|
| **Internal** | {func}`raise_() <StateMachine.raise_>` or `send(..., internal=True)` | Within the current macrostep |
| **External** | {func}`send() <StateMachine.send>` | After the current macrostep ends |

This distinction matters when you trigger events from inside callbacks.
Using `raise_()` ensures the event is handled as part of the current
processing cycle, while `send()` defers it to after the machine reaches
a stable configuration.

```{seealso}
See {ref}`sending-events` for examples of `send()` vs `raise_()`.
```


### Processing loop overview

The following diagram shows the complete processing loop:

```
    send("event")
         │
         ▼
  ┌──────────────┐
  │ External     │
  │ Queue        │◄─────────────────────────────┐
  └──────┬───────┘                              │
         │ pop event                            │
         ▼                                      │
  ┌──────────────────────────────────────┐      │
  │          Macrostep                   │      │
  │                                      │      │
  │   ┌──────────────────────┐           │      │
  │   │ Eventless transitions│◄──┐       │      │
  │   │ enabled?             │   │       │      │
  │   └──────┬───────────────┘   │       │      │
  │     yes  │  no               │       │      │
  │          │   │               │       │      │
  │          │   ▼               │       │      │
  │          │  ┌──────────────┐ │       │      │
  │          │  │ Internal     │ │       │      │
  │          │  │ queue empty? │ │       │      │
  │          │  └──┬───────┬───┘ │       │      │
  │          │  no │  yes  │     │       │      │
  │          │     │       │     │       │      │
  │          │     │       ▼     │       │      │
  │          │     │   Stable    │       │      │
  │          │     │   config ───┼───────┼──────┘
  │          │     │             │       │
  │          ▼     ▼             │       │
  │     ┌──────────────┐        │       │
  │     │  Microstep   │────────┘       │
  │     │  (execute    │                │
  │     │  transitions)│                │
  │     └──────────────┘                │
  │                                     │
  └─────────────────────────────────────┘
```


(rtc-model)=
(rtc model)=
(non-rtc model)=

## Run-to-completion in practice

Consider a state machine where one transition triggers another via an
`after` callback:

```py
>>> from statemachine import StateChart, State

>>> class ServerConnection(StateChart):
...     disconnected = State(initial=True)
...     connecting = State()
...     connected = State(final=True)
...
...     connect = disconnected.to(connecting, after="connection_succeed")
...     connection_succeed = connecting.to(connected)
...
...     def on_connect(self):
...         return "on_connect"
...
...     def on_enter_state(self, event: str, state: State, source: State):
...         print(f"enter '{state.id}' from '{source.id if source else ''}' given '{event}'")
...
...     def on_exit_state(self, event: str, state: State, target: State):
...         print(f"exit '{state.id}' to '{target.id}' given '{event}'")
...
...     def on_transition(self, event: str, source: State, target: State):
...         print(f"on '{event}' from '{source.id}' to '{target.id}'")
...         return "on_transition"
...
...     def after_transition(self, event: str, source: State, target: State):
...         print(f"after '{event}' from '{source.id}' to '{target.id}'")
...         return "after_transition"

```

When `connect` is sent, the `after` callback triggers `connection_succeed`.
Under the RTC model, `connection_succeed` is enqueued and processed only
after `connect` completes:

```py
>>> sm = ServerConnection()
enter 'disconnected' from '' given '__initial__'

>>> sm.send("connect")
exit 'disconnected' to 'connecting' given 'connect'
on 'connect' from 'disconnected' to 'connecting'
enter 'connecting' from 'disconnected' given 'connect'
after 'connect' from 'disconnected' to 'connecting'
exit 'connecting' to 'connected' given 'connection_succeed'
on 'connection_succeed' from 'connecting' to 'connected'
enter 'connected' from 'connecting' given 'connection_succeed'
after 'connection_succeed' from 'connecting' to 'connected'
['on_transition', 'on_connect']

```

Notice that `connect` runs all its phases (exit → on → enter → after) before
`connection_succeed` starts. The `after` callback of `connect` fires while
the machine is still in `connecting` — and only then does `connection_succeed`
begin its own microstep.

```{note}
The `__initial__` event is a synthetic event that the engine fires during
initialization to enter the initial state. It follows the same RTC model
as any other event.
```


(continuous-machines)=

## Chaining transitions

Some use cases require a machine that processes multiple steps automatically
within a single macrostep, driven by internal events or eventless transitions
rather than external calls.


### With `raise_()`

Using {func}`raise_() <StateMachine.raise_>` inside callbacks places events
on the **internal queue**, so they are processed within the current macrostep.
This lets you chain multiple transitions from a single `send()` call:

```py
>>> from statemachine import State, StateChart

>>> class Pipeline(StateChart):
...     start = State("Start", initial=True)
...     step1 = State("Step 1")
...     step2 = State("Step 2")
...     done = State("Done", final=True)
...
...     begin = start.to(step1)
...     advance_1 = step1.to(step2)
...     advance_2 = step2.to(done)
...
...     def on_enter_step1(self):
...         print("  step 1: extract")
...         self.raise_("advance_1")
...
...     def on_enter_step2(self):
...         print("  step 2: transform")
...         self.raise_("advance_2")
...
...     def on_enter_done(self):
...         print("  done: load complete")

>>> sm = Pipeline()
>>> sm.send("begin")
  step 1: extract
  step 2: transform
  done: load complete

>>> [s.id for s in sm.configuration]
['done']

```

All three steps execute within a single macrostep — the caller receives
control back only after the pipeline reaches a stable configuration.


### With eventless transitions

{ref}`Eventless transitions <eventless>` fire automatically whenever their
guard condition is satisfied. Combined with a self-transition, this creates
a loop that keeps running within the macrostep until the condition becomes
false:

```py
>>> from statemachine import State, StateChart

>>> class RetryMachine(StateChart):
...     trying = State("Trying", initial=True)
...     success = State("Success", final=True)
...     failed = State("Failed", final=True)
...
...     # Eventless transitions: fire automatically based on guards
...     trying.to.itself(cond="can_retry")
...     trying.to(failed, cond="max_retries_reached")
...
...     # Event-driven transition (external input)
...     succeed = trying.to(success)
...
...     def __init__(self, max_retries=3):
...         self.attempts = 0
...         self.max_retries = max_retries
...         super().__init__()
...
...     def can_retry(self):
...         return self.attempts < self.max_retries
...
...     def max_retries_reached(self):
...         return self.attempts >= self.max_retries
...
...     def on_enter_trying(self):
...         self.attempts += 1
...         print(f"  attempt {self.attempts}")

>>> sm = RetryMachine(max_retries=3)
  attempt 1
  attempt 2
  attempt 3

>>> [s.id for s in sm.configuration]
['failed']

```

The machine starts, enters `trying` (attempt 1), and the eventless
self-transition keeps firing as long as `can_retry()` returns `True`. Once
the limit is reached, the second eventless transition fires — all within a
single macrostep triggered by initialization.


(thread-safety)=

## Thread safety

State machines are **thread-safe** for concurrent event sending. Multiple threads
can call `send()` or trigger events on the **same state machine instance**
simultaneously — the engine guarantees correct behavior through its internal
locking mechanism.

### How it works

The processing loop uses a non-blocking lock (`threading.Lock`). When a thread
sends an event:

1. The event is placed on the **external queue** (backed by a thread-safe
   `PriorityQueue` from the standard library).
2. If no other thread is currently running the processing loop, the sending
   thread acquires the lock and processes all queued events.
3. If another thread is already processing, the event is simply enqueued and
   will be processed by the thread that holds the lock — no event is lost.

This means that **at most one thread executes transitions at any time**, preserving
the run-to-completion (RTC) guarantee while allowing safe concurrent access.

### What is safe

- **Multiple threads sending events** to the same state machine instance.
- **Reading state** (`current_state_value`, `configuration`) from any thread
  while events are being processed. Note that transient `None` values may be
  observed for `current_state_value` during configuration updates when using
  [`atomic_configuration_update`](behaviour.md#atomic_configuration_update) `= False`
  (the default on `StateChart`, SCXML-compliant). With `atomic_configuration_update = True`
  (the default on `StateMachine`), the configuration is updated atomically at
  the end of the microstep, so `None` is not observed.
- **Invoke handlers** running in background threads or thread executors
  communicate with the parent machine via the thread-safe event queue.

### What to avoid

- **Do not share a state machine instance across threads with the async engine**
  unless you ensure only one event loop drives the machine. The async engine is
  designed for `asyncio` concurrency, not thread-based concurrency.
- **Callbacks execute in the processing thread**, not in the thread that sent
  the event. Design callbacks accordingly (e.g., use locks if they access
  shared external state).
