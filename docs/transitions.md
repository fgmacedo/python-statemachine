(transitions)=

```{testsetup}

>>> from statemachine import StateMachine, State

>>> from tests.examples.traffic_light_machine import TrafficLightMachine

```

# Transitions and events

A machine moves from state to state through transitions. These transitions are
caused by events.


(event)=

## Event

An event is an external signal that something has happened.
They are sent to a state machine, and allow the state machine to react.


An event start a {ref}`transition`, can be thought of as a "cause" that
initiates a change in the state of the system.

In python-statemachine, an event is specified as an attribute of the
statemachine class declaration, or diretly on the `event` parameter on
a {ref}`transition`.


(transition)=

## Transition

In an executing state machine, a transition is the instantaneous transfer
from one state to another.  In a state machine, a transition tells us what
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

```{mermaid}
:align: center

stateDiagram-v2
direction LR
[*] --> green
green --> yellow: cycle
yellow --> red: cycle
red --> green: cycle

```

There're tree transitions, one starting from green to yellow, another from
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

When an {{event}} is sent to a stamemachine:

1. Uses the current {{state}} to check for available transitions.
1. For each possible transition, it checks for those that matches the received {ref}`event`.
1. The destination state, if the transition succeeds, is determined by a transisition
   that an event matches and;
1. All {ref}`validations` and {ref}`guards` passes, including {ref}`actions`
   atached to the `on_<event>` and `before_<event>` callbacks.


## Triggering events


By direct calling the event:

```py
>>> machine = TrafficLightMachine()

>>> machine.cycle()
'Running cycle from green to yellow'

>>> machine.current_state.identifier
'yellow'

```

In a running (interpreted) machine, events are `sent`:

```py
>>> machine.run("cycle")
'Running cycle from yellow to red'

>>> machine.current_state.identifier
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
>>> machine.current_state.identifier
'red'

>>> machine.cycle()
'Running cycle from red to green'

>>> machine.current_state.identifier
'green'

```

(validators-and-guards)=
## Validators and guards

Validations and Guards are checked before an transition is started. They are meant to stop a
transition to occur.

The main difference, is that {ref}`validators` raise exceptions to stop the flow, and ()[#guards]
act like predicates that should resolve for ``boolean``.

### Guards

Also known as **Conditional transition**.

A guard is a condition that may be checked when a statechart wants to handle
an event. A guard is declared on the transition, and when that transition
would trigger, then the guard (if any) is checked.  If the guard is true
then the transition does happen. If the guard is false, the transition
is ignored.

When transitions have guards, then it's possible to define two or more
transitions for the same event from the same state, i.e. that a state has
two (or more) transitions for the same event.  When the event happens, then
the guarded transitions are checked, one by one, and the first transition
whose guard is true will be used, the others will be ignored.

A guard is generally a boolean function or boolean variable.  It must be
evaluated synchronously — A guard can for example not wait for a future or
promise to resolve — and should return immediately.

A guard function must not have any side effects.  Side effects are reserved
for actions.

There are two variations of Guard clauses available:


Conditions
: A list of conditions, acting like predicates. A transition is only allowed to occur if
all conditions evaluates to ``True``.

Unless
: Same as conditions, but the transition is allowed if they evaluates fo ``False``.

### Validators


Are like {ref}`guards`, but instead of evaluating to boolean, they are expected to raise an
exception to stop the flow. It may be useful for imperative style programming, when you don't
wanna to continue evaluating other possible transitions.


### Example


Consider this example:

```py

class InvoiceStateMachine(StateMachine):
    unpaid = State("unpaid", initial=True)
    paid = State("paid")
    failed = State("failed")

    pay = (
        unpaid.to(paid, conditions="payment_success")
        | failed.to(paid)
        | unpaid.to(failed)
    )

    def payment_success(self, event_data):
        return <validation logic goes here>

```


Reference: [Statecharts](https://statecharts.dev/).
