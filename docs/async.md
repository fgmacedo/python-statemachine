(async)=
# Async support

```{seealso}
New to statecharts? See [](concepts.md) for an overview of how states,
transitions, events, and actions fit together.
```

The public API is the same for synchronous and asynchronous code. If the
state machine has at least one `async` callback, the engine switches to
{ref}`AsyncEngine <asyncengine>` automatically — no configuration needed.

All statechart features — compound states, parallel states, history
pseudo-states, eventless transitions, `done.state` events — work
identically in both engines.


## Writing async callbacks

Declare any callback as `async def` and the engine handles the rest:

```py
>>> class AsyncStateMachine(StateChart):
...     initial = State("Initial", initial=True)
...     final = State("Final", final=True)
...
...     keep = initial.to.itself(internal=True)
...     advance = initial.to(final)
...
...     async def on_advance(self):
...         return 42

>>> async def run_sm():
...     sm = AsyncStateMachine()
...     result = await sm.advance()
...     print(f"Result is {result}")
...     print(list(sm.configuration_values))

>>> asyncio.run(run_sm())
Result is 42
['final']

```

### Using from synchronous code

The same state machine can be used from a synchronous context — even
without a running `asyncio` loop. The engine creates one internally
with `asyncio.new_event_loop()` and awaits callbacks using
`loop.run_until_complete()`:

```py
>>> sm = AsyncStateMachine()
>>> result = sm.advance()
>>> print(f"Result is {result}")
Result is 42
>>> print(list(sm.configuration_values))
['final']

```


(initial state activation)=

## Initial state activation

In async code, Python cannot `await` during `__init__`, so the initial
state is **not** activated at instantiation time. If you inspect
`configuration` immediately after creating the instance, it won't reflect
the initial state:

```py
>>> async def show_problem():
...     sm = AsyncStateMachine()
...     print(list(sm.configuration_values))

>>> asyncio.run(show_problem())
[None]

```

To fix this, explicitly await
{func}`activate_initial_state() <statemachine.StateChart.activate_initial_state>`
before inspecting the configuration:

```py
>>> async def correct_init():
...     sm = AsyncStateMachine()
...     await sm.activate_initial_state()
...     print(list(sm.configuration_values))

>>> asyncio.run(correct_init())
['initial']

```

```{tip}
If you don't inspect the configuration before sending the first event,
you can skip this step — the first `send()` activates the initial state
automatically.
```

```py
>>> async def auto_activate():
...     sm = AsyncStateMachine()
...     await sm.keep()  # activates initial state before handling the event
...     print(list(sm.configuration_values))

>>> asyncio.run(auto_activate())
['initial']

```


## Concurrent event sending

A benefit exclusive to the async engine: when multiple coroutines send
events concurrently (e.g., via `asyncio.gather`), each caller receives
its own event's result — even though only one coroutine runs the
processing loop at a time. The sync engine does not support this pattern.

```py
>>> class ConcurrentSC(StateChart):
...     s1 = State(initial=True)
...     s2 = State()
...     s3 = State(final=True)
...
...     step1 = s1.to(s2)
...     step2 = s2.to(s3)
...
...     async def on_step1(self):
...         return "result_1"
...
...     async def on_step2(self):
...         return "result_2"

>>> async def run_concurrent():
...     import asyncio as _asyncio
...     sm = ConcurrentSC()
...     await sm.activate_initial_state()
...     r1, r2 = await _asyncio.gather(
...         sm.send("step1"),
...         sm.send("step2"),
...     )
...     return r1, r2

>>> asyncio.run(run_concurrent())
('result_1', 'result_2')

```

Under the hood, the async engine attaches an `asyncio.Future` to each
externally enqueued event. The coroutine that acquires the processing lock
resolves each event's future as it processes the queue. Callers that didn't
acquire the lock simply `await` their future.

```{note}
Futures are only created for **external** events sent from outside the
processing loop. Events triggered from within callbacks (via `send()` or
`raise_()`) follow the {ref}`run-to-completion <rtc-model>` model — they
are enqueued and processed within the current macrostep.
```

If an exception occurs during processing (with `error_on_execution=False`),
the exception is routed to the caller whose event caused it. Other callers
whose events were still pending will also receive the exception, since the
processing loop clears the queue on failure.


(syncengine)=
(asyncengine)=

## Engine selection

The engine is selected automatically when the state machine is
instantiated, based on the registered callbacks:

| Outer scope | Async callbacks? | Engine | Event loop |
|---|---|---|---|
| Sync | No | SyncEngine | None |
| Sync | Yes | AsyncEngine | Creates internal loop |
| Async | No | SyncEngine | None |
| Async | Yes | AsyncEngine | Reuses running loop |

**Outer scope** is the context where the state machine instance is created.
**Async callbacks** means at least one `async def` callback or condition is
declared on the machine, its model, or its listeners.

```{note}
All callbacks run on the same thread they are called from. Mixing
synchronous and asynchronous code is supported but requires care —
avoid sharing a state machine instance across threads without external
synchronization.
```


```{seealso}
See {ref}`processing model <macrostep-microstep>` for how the engine
processes events, and {ref}`behaviour` for the behavioral attributes
that affect processing.
```
