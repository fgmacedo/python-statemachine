# Async

```{versionadded} 2.3.0
Support for async code was added!
```

The {ref}`StateMachine` fully supports asynchronous code. You can write async {ref}`actions`, {ref}`guards`, and {ref}`events` triggers, while maintaining the same external API for both synchronous and asynchronous codebases.

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
>>> class AsyncStateMachine(StateMachine):
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
...     print(sm.current_state)

>>> asyncio.run(run_sm())
Result is 42
Final

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
>>> print(sm.current_state)
Final

```


(initial state activation)=
## Initial State Activation for Async Code


If **on async code** you perform checks against the `current_state`, like a loop `while sm.current_state.is_final:`, then you must manually
await for the  [activate initial state](statemachine.StateMachine.activate_initial_state) to be able to check the current state.

```{hint}
This manual initial state activation on async is because Python don't allow awaiting at class initalization time and the initial state activation may contain async callbacks that must be awaited.
```

If you don't do any check for current state externally, just ignore this as the initial state is activated automatically before the first event trigger is handled.

You get an error checking the current state before the initial state activation:

```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     print(sm.current_state)

>>> asyncio.run(initialize_sm())
Traceback (most recent call last):
...
InvalidStateValue: There's no current state set. In async code, did you activate the initial state? (e.g., `await sm.activate_initial_state()`)

```

You can activate the initial state explicitly:


```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     await sm.activate_initial_state()
...     print(sm.current_state)

>>> asyncio.run(initialize_sm())
Initial

```

Or just by sending an event. The first event activates the initial state automatically
before the event is handled:

```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     await sm.keep()  # first event activates the initial state before the event is handled
...     print(sm.current_state)

>>> asyncio.run(initialize_sm())
Initial

```
