# Processing model

In the literature, It's expected that all state-machine events should execute on a
[run-to-completion](https://en.wikipedia.org/wiki/UML_state_machine#Run-to-completion_execution_model)
(RTC) model.

> All state machine formalisms, including UML state machines, universally assume that a state machine
> completes processing of each event before it can start processing the next event. This model of
> execution is called run to completion, or RTC.

The main point is: What should happen if the state machine triggers nested events while processing a parent event?

```{hint}
The importance of this decision depends on your state machine definition. Also the difference between RTC
and non-RTC processing models is more pronounced in a multi-threaded system than in a single-threaded system.
In other words, even if you run in {ref}`Non-RTC model`, only one external {ref}`event` will be
handled at a time and all internal events will run before the next external event is called,
so you only notice the difference if your state machine definition has nested event triggers while
processing these external events.
```

There are two distinct models for processing events in the library. The default is to run in
{ref}`RTC model` to be compliant with the specs, where the {ref}`event` is put on a
queue before processing. You can also configure your state machine to run in
{ref}`Non-RTC model`, where the {ref}`event` will be run immediately.

Consider this state machine:

```py
>>> from statemachine import StateMachine, State

>>> class ServerConnection(StateMachine):
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

If the machine is in `rtc` mode, the event is put on a queue.

```{note}
While processing the queue items, if others events are generated, they will be processed sequentially.
```

Running the above state machine will give these results on the RTC model:

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

## Non-RTC model

```{deprecated} 2.3.2
`StateMachine.rtc` option is deprecated. We'll keep only the **run-to-completion** (RTC) model.
```

In contrast, in a non-RTC (synchronous) processing model, the state machine starts executing nested events
while processing a parent event. This means that when an event is triggered, the state machine
chains the processing when another event was triggered as a result of the first event.

```{warning}
This can lead to complex and unpredictable behavior in the system if your state-machine definition triggers **nested
events**.
```

If your state machine does not trigger nested events while processing a parent event,
and you plan to use the API in an _imperative programming style_, you can consider using the synchronous mode (non-RTC).

In this model, you can think of events as analogous to simple method calls.

```{note}
While processing the {ref}`event`, if others events are generated, they will also be processed immediately, so a **nested** behavior happens.
```

Running the above state machine will give these results on the non-RTC (synchronous) model:

```py
>>> sm = ServerConnection(rtc=False)
enter 'disconnected' from '' given '__initial__'

>>> sm.send("connect")
exit 'disconnected' to 'connecting' given 'connect'
on 'connect' from 'disconnected' to 'connecting'
enter 'connecting' from 'disconnected' given 'connect'
exit 'connecting' to 'connected' given 'connection_succeed'
on 'connection_succeed' from 'connecting' to 'connected'
enter 'connected' from 'connecting' given 'connection_succeed'
after 'connection_succeed' from 'connecting' to 'connected'
after 'connect' from 'disconnected' to 'connecting'
['on_transition', 'on_connect']

```

```{note}
Note that the events `connect` and `connection_succeed` are nested, and the `connect.after`
unexpectedly only runs after `connection_succeed.after`.
```
