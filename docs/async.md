# Async

```{versionadded} 2.3.0
Support for async code was added!
```

The {ref}`StateChart` fully supports asynchronous code. You can write async {ref}`actions`, {ref}`guards`, and {ref}`events` triggers, while maintaining the same external API for both synchronous and asynchronous codebases.

This is achieved through a new concept called **engine**, an internal strategy pattern abstraction that manages transitions and callbacks.

There are two engines, {ref}`SyncEngine` and {ref}`AsyncEngine`.


## Sync vs async engines

Engines are internal and are activated automatically by inspecting the registered callbacks in the following scenarios.


```{list-table} Sync vs async engines
:header-rows: 1

*   - Outer scope
    - Async callbacks?
    - Engine
    - Creates internal loop
    - Reuses external loop
*   - Sync
    - No
    - SyncEngine
    - No
    - No
*   - Sync
    - Yes
    - AsyncEngine
    - Yes
    - No
*   - Async
    - No
    - SyncEngine
    - No
    - No
*   - Async
    - Yes
    - AsyncEngine
    - No
    - Yes

```

Outer scope
: The context in which the state machine **instance** is created.

Async callbacks?
: Indicates whether the state machine has declared asynchronous callbacks or conditions.

Engine
: The engine that will be utilized.

Creates internal loop
: Specifies whether the state machine initiates a new event loop if no [asyncio loop is running](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop).

Reuses external loop
: Indicates whether the state machine reuses an existing [asyncio loop](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.get_running_loop) if one is already running.



```{note}
All handlers will run on the same thread they are called. Therefore, mixing synchronous and asynchronous code is not recommended unless you are confident in your implementation.
```

### SyncEngine
Activated if there are no async callbacks. All code runs exactly as it did before version 2.3.0.
There's no event loop.

### AsyncEngine
Activated if there is at least one async callback. The code runs asynchronously and requires a running event loop, which it will create if none exists.



## Asynchronous Support

We support native coroutine callbacks using asyncio, enabling seamless integration with asynchronous code. There is no change in the public API of the library to work with asynchronous codebases.


```{seealso}
See {ref}`sphx_glr_auto_examples_air_conditioner_machine.py` for an example of
async code with a state machine.
```


```py
>>> class AsyncStateMachine(StateChart):
...     initial = State('Initial', initial=True)
...     final = State('Final', final=True)
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

## Sync codebase with async callbacks

The same state machine with async callbacks can be executed in a synchronous codebase,
even if the calling context don't have an asyncio loop.

If needed, the state machine will create a loop using `asyncio.new_event_loop()` and callbacks will be awaited using `loop.run_until_complete()`.


```py
>>> sm = AsyncStateMachine()
>>> result = sm.advance()
>>> print(f"Result is {result}")
Result is 42
>>> print(list(sm.configuration_values))
['final']

```


(initial state activation)=
## Initial State Activation for Async Code


If **on async code** you perform checks against the `configuration`, like a loop `while not sm.is_terminated:`, then you must manually
await for the  [activate initial state](statemachine.StateChart.activate_initial_state) to be able to check the configuration.

```{hint}
This manual initial state activation on async is because Python don't allow awaiting at class initalization time and the initial state activation may contain async callbacks that must be awaited.
```

If you don't do any check for configuration externally, just ignore this as the initial state is activated automatically before the first event trigger is handled.

You get an error checking the configuration before the initial state activation:

```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     print(list(sm.configuration_values))

>>> asyncio.run(initialize_sm())
[None]

```

You can activate the initial state explicitly:


```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     await sm.activate_initial_state()
...     print(list(sm.configuration_values))

>>> asyncio.run(initialize_sm())
['initial']

```

Or just by sending an event. The first event activates the initial state automatically
before the event is handled:

```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     await sm.keep()  # first event activates the initial state before the event is handled
...     print(list(sm.configuration_values))

>>> asyncio.run(initialize_sm())
['initial']

```

## StateChart async support

```{versionadded} 3.0.0
```

`StateChart` works identically with the async engine. All statechart features —
compound states, parallel states, history pseudo-states, eventless transitions,
and `done.state` events — are fully supported in async code. The same
`activate_initial_state()` pattern applies:

```python
async def run():
    sm = MyStateChart()
    await sm.activate_initial_state()
    await sm.send("event")
```

### Async-specific limitations

- **Initial state activation**: In async code, you must `await sm.activate_initial_state()`
  before inspecting `sm.configuration`. In sync code this happens
  automatically at instantiation time.
- **Delayed events**: Both sync and async engines support `delay=` on `send()`. The async
  engine uses `asyncio.sleep()` internally, so it integrates naturally with event loops.
- **Thread safety**: The processing loop uses a non-blocking lock (`_processing.acquire`).
  All callbacks run on the same thread they are called from — do not share a state machine
  instance across threads without external synchronization.
