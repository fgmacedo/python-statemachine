# Processing model

In the literature, It's expected that all state-machine events should execute on a
[run-to-completion](https://en.wikipedia.org/wiki/UML_state_machine#Run-to-completion_execution_model)
(RTC) model.

> All state machine formalisms, including UML state machines, universally assume that a state machine
> completes processing of each event before it can start processing the next event. This model of
> execution is called run to completion, or RTC.

The main point is: What should happen if the state machine triggers nested events while processing a parent event?

This library atheres to the {ref}`RTC model` to be compliant with the specs, where the {ref}`event` is put on a
queue before processing.

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

## RTC model

In a run-to-completion (RTC) processing model (**default**), the state machine executes each event to completion before processing the next event. This means that the state machine completes all the actions associated with an event before moving on to the next event. This guarantees that the system is always in a consistent state.

Internally, the events are put on a queue before processing.

```{note}
While processing the queue items, if others events are generated, they will be processed sequentially in FIFO order.
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
Note that the events `connect` and `connection_succeed` are executed sequentially, and the `connect.after` runs on the expected order.
```
