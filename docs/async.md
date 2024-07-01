# Async

```{versionadded} 2.3.0
Support for async code was added!
```

The {ref}`StateMachine` fully supports asynchronous code. You can write async {ref}`actions`, {ref}`guards`, and {ref}`event` triggers, while maintaining the same external API for both synchronous and asynchronous codebases.

This is achieved through a new concept called "engine," an internal strategy pattern abstraction that manages transitions and callbacks.

There are two engines:

SyncEngine
: Activated if there are no async callbacks. All code runs exactly as it did before version 2.3.0.

AsyncEngine
: Activated if there is at least one async callback. The code runs asynchronously and requires a running event loop, which it will create if none exists.

These engines are internal and are activated automatically by inspecting the registered callbacks in the following scenarios:


```{list-table} Sync vs async engines
:widths: 15 10 25 10 10
:header-rows: 1

*   - Outer scope
    - Async callbacks?
    - Engine
    - Creates internal loop
    - Reuses external loop
*   - Sync
    - No
    - Sync
    - No
    - No
*   - Sync
    - Yes
    - Async
    - Yes
    - No
*   - Async
    - No
    - Sync
    - No
    - No
*   - Async
    - Yes
    - Async
    - No
    - Yes

```


```{note}
All handlers will run on the same thread they are called. Therefore, mixing synchronous and asynchronous code is not recommended unless you are confident in your implementation.
```

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

The same state machine can be executed in a synchronous codebase, even if it contains async callbacks. The callbacks will be awaited using `asyncio.get_event_loop()` if needed.


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


If you perform checks against the `current_state`, like a loop `while sm.current_state.is_final:`, then on async code you must manually
await for the  [activate initial state](statemachine.StateMachine.activate_initial_state) to be able to check the current state.

If you don't do any check for current state externally, just ignore this as the initial state is activated automatically before the first event trigger is handled.


```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     await sm.activate_initial_state()
...     return sm

>>> sm = asyncio.run(initialize_sm())
>>> print(sm.current_state)
Initial

```

```{hint}
This manual initial state activation on async is because Python don't allow awaiting at class initalization time and the initial state activation may contain async callbacks that must be awaited.
```
