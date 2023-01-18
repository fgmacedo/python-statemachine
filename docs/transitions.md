(transitions)=

```{testsetup}

>>> from statemachine import StateMachine, State

>>> from tests.examples.traffic_light_machine import TrafficLightMachine

```

# Transitions and events

A machine moves from state to state through transitions. These transitions are
caused by events.


## Event

An event is an external signal that something has happened.
They are send to a state machine and allow the state machine to react.

An event starts a {ref}`transition`, can be thought of as a "cause" that
initiates a change in the state of the system.

In python-statemachine, an event is specified as an attribute of the
statemachine class declaration or directly on the {ref}`event` parameter on
a {ref}`transition`.


## Transition

In an executing state machine, a transition is the instantaneous transfer
from one state to another. In a state machine, a transition tells us what
happens when an {ref}`event` occurs.

A self transition is a transition that goes from and to the same state.

A transition can define actions that will be executed whenever that transition
is executed.

```{eval-rst}
.. autoclass:: statemachine.transition.Transition
    :members:
```

(self-transition)=

### Self transition

A transition that goes from a state to itself.

Syntax:

```py
>>> draft = State("Draft")

>>> draft.to.itself()
TransitionList([Transition(State('Draft', ...

```

### Example

Consider this traffic light machine as example:

![TrafficLightMachine](images/traffic_light_machine.png)


There're three transitions, one starting from green to yellow, another from
yellow to red, and another from red back to green. All these transitions
are triggered by the same {ref}`event` called `cycle`.

This statemachine could be expressed in python-statemachine as:


```{literalinclude} ../tests/examples/traffic_light_machine.py
:language: python
:linenos:
:emphasize-lines: 18
```

At line 18, you can say that this code defines three transitions:

* `green.to(yellow)`
* `yellow.to(red)`
* `red.to(green)`

And these transitions are assigned to the {ref}`event` `cycle` defined at
class level.

When an {ref}`event` is send to a statemachine:

1. Uses the current {ref}`state` to check for available transitions.
1. For each possible transition, it checks for those that matches the received {ref}`event`.
1. The target state, if the transition succeeds, is determined by a transition
   that an event matches and;
1. All {ref}`validators-and-guards`, including {ref}`actions`
   attached to the `on_<event>` and `before_<event>` callbacks.


## Triggering events


By direct calling the event:

```py
>>> machine = TrafficLightMachine()

>>> machine.cycle()
'Running cycle from green to yellow'

>>> machine.current_state.id
'yellow'

```

In a running (interpreted) machine, events are `send`:

```py
>>> machine.send("cycle")
'Running cycle from yellow to red'

>>> machine.current_state.id
'red'

```

You can also pass positional and keyword arguments, that will be propagated
to the actions. On this example, the :code:`TrafficLightMachine` implements
an action that `echoes` back the params informed.

```{literalinclude} ../tests/examples/traffic_light_machine.py
    :language: python
    :linenos:
    :emphasize-lines: 10
    :lines: 12-15
```


This action is executed before the transition associated with `cycle` event is activated, so you
can also raise an exception at this point to stop a transition to occur.

```py
>>> machine.current_state.id
'red'

>>> machine.cycle()
'Running cycle from red to green'

>>> machine.current_state.id
'green'

```
