Transitions and events
======================

A machine moves from state to state through transitions. These transitions are
caused by events.


.. _event:


Event
-----

An event is an external signal that something has happened.
They are sent to a state machine, and allow the state machine to react.


An event triggers a :ref:`transition`, can be thought of as a "cause" that
initiates a change in the state of the system.

In python-statemachine, an event is specified as an attribute of the
statemachine class declaration.


.. _transition:

Transition
----------

In an executing state machine, a transition is the instantaneous transfer
from one state to another.  In a state machine, a transition tells us what
happens when an :ref:`event` occurs.

A self transition is a transition that goes from and to the same state.

A transition can define actions that will be executed whenever that transition
is executed.


Example
-------

Consider this traffic light machine as example:

.. mermaid::
    :align: center

    stateDiagram-v2
    direction LR
    [*] --> green
    green --> yellow: cycle
    yellow --> red: cycle
    red --> green: cycle

There're tree transitions, one starting from green to yellow, another from
yellow to red, and another from red back to green. All these transitions
are triggered by the same :ref:`event` called :code:`cycle`.

This statemachine could be expressed in python-statemachine as:


.. literalinclude:: ../tests/examples/traffic_light_machine.py
   :language: python
   :linenos:
   :emphasize-lines: 10


At line 10, you can say that this code defines three transitions:

* :code:`green.to(yellow)`
* :code:`yellow.to(red)`
* :code:`red.to(green)`

And these transitions are assigned to the event :code:`cycle` defined at
class level.

The destination state is determined by the event and the current state.


Triggering events
-----------------

.. testsetup::

    >>> from tests.examples.traffic_light_machine import TrafficLightMachine


By direct calling the event:

>>> machine = TrafficLightMachine()
>>> machine.cycle()
'Running cycle from green to yellow'
>>> machine.current_state.identifier
'yellow'

In a running (interpreted) machine, events are `sent`:

>>> machine.run("cycle")
'Running cycle from yellow to red'
>>> machine.current_state.identifier
'red'

You can also pass positional and keyword arguments, that will be propagated
to the actions. On this example, the :code:`TrafficLightMachine` implements
an action that `echoes` back the params informed.

.. literalinclude:: ../tests/examples/traffic_light_machine.py
    :language: python
    :linenos:
    :emphasize-lines: 10
    :lines: 12-15

This action is executed
before the transition associated with :code:`cycle` event is activated, so you
can also raise an exception at this point to stop a transition to occur.

>>> machine.current_state.identifier
'red'
>>> machine.cycle()
'Running cycle from red to green'
>>> machine.current_state.identifier
'green'


Guards
------

Also known as Conditional transition

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


**conditions**

A list of conditions, acting like predicates. A transition is only allowed to occur if
all conditions evaluates to ``True``.

**unless**

Same as conditions, but the transition is allowed if they evaluates fo ``False``.


Example
.......

Consider this example:

.. code-block:: python

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



Reference: `Statecharts <https://statecharts.dev/>`_.
