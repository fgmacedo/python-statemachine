(timeout)=
# State timeouts

A common need is preventing a state machine from getting stuck — for example,
a "waiting for response" state that should time out after a few seconds. The
{func}`~statemachine.contrib.timeout.timeout` helper makes this easy by
leveraging the {ref}`invoke <invoke>` system: a background timer starts when
the state is entered and is automatically cancelled when the state is exited.

## Basic usage

When the timeout expires and no custom event is specified, the standard
`done.invoke.<state>` event fires — just like any other invoke completion:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.contrib.timeout import timeout

>>> class WaitingMachine(StateChart):
...     waiting = State(initial=True, invoke=timeout(5))
...     done = State(final=True)
...     done_invoke_waiting = waiting.to(done)

>>> sm = WaitingMachine()
>>> sm.waiting.is_active
True

```

In this example, if the machine stays in `waiting` for 5 seconds,
`done.invoke.waiting` fires and the machine transitions to `done`.
If any other event causes a transition out of `waiting` first,
the timer is cancelled automatically.


## Custom timeout event

Use the `on` parameter to send a specific event name instead of
`done.invoke.<state>`. This is useful when you want to distinguish
timeouts from normal completions:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.contrib.timeout import timeout

>>> class RequestMachine(StateChart):
...     requesting = State(initial=True, invoke=timeout(30, on="request_timeout"))
...     timed_out = State(final=True)
...     request_timeout = requesting.to(timed_out)

>>> sm = RequestMachine()
>>> sm.requesting.is_active
True

```

## Composing with other invoke handlers

Since `timeout()` returns a standard invoke handler, you can combine it with
other handlers in a list. The first handler to complete and trigger a transition
wins — the state exit cancels everything else:

```py
>>> from statemachine import State, StateChart
>>> from statemachine.contrib.timeout import timeout

>>> def fetch_data():
...     return {"status": "ok"}

>>> class LoadingMachine(StateChart):
...     loading = State(initial=True, invoke=[fetch_data, timeout(30, on="too_slow")])
...     ready = State(final=True)
...     stuck = State(final=True)
...     done_invoke_loading = loading.to(ready)
...     too_slow = loading.to(stuck)

>>> sm = LoadingMachine()
>>> sm.ready.is_active
True

```

In this example:
- If `fetch_data` completes within 30 seconds, `done.invoke.loading` fires
  and transitions to `ready`, cancelling the timeout.
- If 30 seconds pass first, `too_slow` fires and transitions to `stuck`,
  cancelling the `fetch_data` invoke.


## API reference

See {func}`~statemachine.contrib.timeout.timeout` in the {ref}`API docs <api>`.
