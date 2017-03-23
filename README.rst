===============================
Python State Machine
===============================


.. image:: https://img.shields.io/pypi/v/python-statemachine.svg
        :target: https://pypi.python.org/pypi/python-statemachine

.. image:: https://img.shields.io/travis/fgmacedo/python-statemachine.svg
        :target: https://travis-ci.org/fgmacedo/python-statemachine

.. image:: https://readthedocs.org/projects/python-statemachine/badge/?version=latest
        :target: https://python-statemachine.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fgmacedo/python-statemachine/shield.svg
     :target: https://pyup.io/repos/github/fgmacedo/python-statemachine/
     :alt: Updates


Python finite-state machines made easy.


* Free software: MIT license
* Documentation: https://python-statemachine.readthedocs.io.


Getting started
===============

To install Python State Machine, run this command in your terminal:

.. code-block:: console

    $ pip install python-statemachine


Import the statemachine::

    from statemachine import StateMachine, State


Define your state machine::


    class TrafficLightMachine(StateMachine):
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        slowdown = green.to(yellow)
        stop = yellow.to(green)
        go = red.to(green)


You can now create an instance::

    >>> machine = TrafficLightMachine()

And inspect about the current state::

    >>> machine.current_state
    State('Green', identifier='green', value='green', initial=True)
    >>> machine.current_state == TrafficLightMachine.green == machine.green
    True

For each state, there's a dinamically created property in the form ``is_<state.identifier>``, that
returns ``True`` if the current status matches the query::

    >>> machine.is_green
    True
    >>> machine.is_yellow
    False
    >>> machine.is_red
    False

Query about metadata::

    >>> [s.identifier for s in m.states]
    ['green', 'red', 'yellow']
    >>> [t.identifier for t in m.transitions]
    ['go', 'slowdown', 'stop']

Call a transition::

    >>> machine.slowdown()

And check for the current status::

    >>> machine.current_state
    State('Yellow', identifier='yellow', value='yellow', initial=False)
    >>> machine.is_yellow
    True

You can't run a transition from an invalid state::

    >>> machine.is_yellow
    True
    >>> machine.slowdown()
    Traceback (most recent call last):
    ...
    LookupError: Can't slowdown when in Yellow.

You can also trigger events in an alternative way, calling the ``run(<transition.identificer>)`` method::

    >>> machine.is_yellow
    True
    >>> machine.run('stop')
    >>> machine.is_red
    True

A state machine can be instantiated with an initial value::

    >>> machine = TrafficLightMachine(start_value='red')
    >>> machine.is_red
    True


Models
------

If you need to persist the current state on another object, or you're using the
state machine to control the flow of another object, you can pass this object
to the ``StateMachine`` constructor::

    >>> class MyModel(object):
    ...     def __init__(self, state):
    ...         self.state = state
    ...
    >>> obj = MyModel(state='red')
    >>> machine = TrafficLightMachine(obj)
    >>> machine.is_red
    True
    >>> obj.state
    'red'
    >>> obj.state = 'green'
    >>> machine.is_green
    True
    >>> machine.slowdown()
    >>> obj.state
    'yellow'
    >>> machine.is_yellow
    True


Events
------

Docs needed.
