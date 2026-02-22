(processing-model)=
(processing model)=

# Processing model

In the literature, it's expected that all state-machine events should execute on a
[run-to-completion](https://en.wikipedia.org/wiki/UML_state_machine#Run-to-completion_execution_model)
(RTC) model.

> All state machine formalisms, including UML state machines, universally assume that a state machine
> completes processing of each event before it can start processing the next event. This model of
> execution is called run to completion, or RTC.

The main point is: What should happen if the state machine triggers nested events while
processing a parent event?

This library adheres to the {ref}`RTC model <rtc-model>` to be compliant with the specs, where
the {ref}`event` is put on a queue before processing.

Consider this state machine:

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

(rtc-model)=
(rtc model)=
(non-rtc model)=

## RTC model

In a run-to-completion (RTC) processing model (**default**), the state machine executes each
event to completion before processing the next event. This means that the state machine
completes all the actions associated with an event before moving on to the next event. This
guarantees that the system is always in a consistent state.

Internally, the events are put on a queue before processing.

```{note}
While processing the queue items, if other events are generated, they will be processed
sequentially in FIFO order.
```

Running the above state machine will give these results:

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

```{note}
Note that the events `connect` and `connection_succeed` are executed sequentially, and the
`connect.after` runs in the expected order.
```


(macrostep-microstep)=

## Macrosteps and microsteps

The processing loop is organized into two levels: **macrosteps** and **microsteps**.
Understanding these concepts is key to predicting how the engine processes events,
especially with {ref}`eventless transitions <eventless>`, internal events
({func}`raise_() <StateMachine.raise_>`), and {ref}`error.execution <error-execution>`.

### Microstep

A **microstep** is the smallest unit of processing. It takes a set of enabled transitions
and executes them atomically:

1. Run `before` callbacks.
2. Exit source states (run `on_exit` callbacks).
3. Execute transition actions (`on` callbacks).
4. Enter target states (run `on_enter` callbacks).
5. Run `after` callbacks.

If an error occurs during steps 1–4 and `error_on_execution` is enabled, the error is
caught at the **block level** — meaning remaining actions in that block are skipped, but
the microstep continues and `after` callbacks still run. Each phase (exit, `on`, enter)
is an independent block, so an error in the transition `on` action does not prevent target
states from being entered. See {ref}`block-level error catching <error-execution>` and the
{ref}`cleanup / finalize pattern <sphx_glr_auto_examples_statechart_cleanup_machine.py>`.

### Macrostep

A **macrostep** is a complete processing cycle triggered by a single external event. It
consists of one or more microsteps and only ends when the machine reaches a **stable
configuration** — a state where no eventless transitions are enabled and the internal
queue is empty.

Within a single macrostep, the engine repeats:

1. **Check eventless transitions** — transitions without an event trigger that fire
   automatically when their guard conditions are met.
2. **Drain the internal queue** — events placed by {func}`raise_() <StateMachine.raise_>`
   are processed immediately, before any external events.
3. If neither step produced a transition, the macrostep is **done**.

After the macrostep completes, the engine picks the next event from the **external queue**
(placed by {func}`send() <StateMachine.send>`) and starts a new macrostep.

### Event queues

The engine maintains two separate FIFO queues:

| Queue        | How to enqueue                                                 | When processed                    |
|--------------|----------------------------------------------------------------|-----------------------------------|
| **Internal** | {func}`raise_() <StateMachine.raise_>` or `send(..., internal=True)` | Within the current macrostep      |
| **External** | {func}`send() <StateMachine.send>`                             | After the current macrostep ends  |

This distinction matters when you trigger events from inside callbacks. Using `raise_()`
ensures the event is handled as part of the current processing cycle, while `send()` defers
it to after the machine reaches a stable configuration.

```{seealso}
See {ref}`triggering-events` for examples of `send()` vs `raise_()`.
```

### Processing loop overview

The following diagram shows the complete processing loop algorithm:

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

(continuous-machines)=

## Continuous state machines

Most state machines are driven by external events — you call `send()` and the machine
responds. But some use cases require a machine that **processes multiple steps
automatically** within a single macrostep, driven by eventless transitions and internal
events rather than external calls.

### Chaining with `raise_()`

Using {func}`raise_() <StateMachine.raise_>` inside callbacks places events on the internal
queue, so they are processed within the current macrostep. This lets you chain multiple
transitions from a single `send()` call:

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

All three steps execute within a single macrostep — the caller receives control back only
after the pipeline reaches a stable configuration.

### Self-loop with eventless transitions

{ref}`Eventless transitions <eventless>` fire automatically whenever their guard condition
is satisfied. A self-transition with a guard creates a loop that keeps running within the
macrostep until the condition becomes false:

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

The machine starts, enters `trying` (attempt 1), and the eventless self-transition keeps
firing as long as `can_retry()` returns `True`. Once the limit is reached, the eventless
`give_up` transition fires — all within a single macrostep triggered by initialization.
