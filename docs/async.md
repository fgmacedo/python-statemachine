# Async

```{versionadded} 2.3.0
Support for async code was added!
```

The {ref}`StateMachine` has full async suport. You can write async {ref}`actions`, {ref}`guards` and {ref}`event` triggers.

Keeping the same external API do interact both on sync or async codebases.

```{note}
All the handlers will run on the same thread they're called. So it's not recommended to mix sync with async code unless
you know what you're doing.
```

## Asynchronous Support

We support native coroutine using asyncio, enabling seamless integration with asynchronous code.
There's no change on the public API of the library to work on async codebases.

One requirement is that when running on an async code, you must manually await for the {ref}`initial state activation` to be able to check the current state.


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

## Sync codebase with async handlers

The same state machine can be executed on a sync codebase, even if it contains async handlers. The handlers will be
awaited on an `asyncio.get_event_loop()` if needed.

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

When working with asynchronous state machines from async code, users must manually [activate initial state](statemachine.StateMachine.activate_initial_state) to be able to check the current state. This change ensures proper state initialization and
execution flow given that Python don't allow awaiting at class initalization time and the initial state activation
may contain async callbacks that must be awaited.

```py
>>> async def initialize_sm():
...     sm = AsyncStateMachine()
...     # await sm.activate_initial_state()
...     return sm

>>> sm = asyncio.run(initialize_sm())
>>> print(sm.current_state)
Initial

```
