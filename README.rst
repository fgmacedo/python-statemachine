====================
Python State Machine
====================


.. image:: https://img.shields.io/pypi/v/python-statemachine.svg
        :target: https://pypi.python.org/pypi/python-statemachine

.. image:: https://travis-ci.org/fgmacedo/python-statemachine.svg?branch=master
        :target: https://travis-ci.org/fgmacedo/python-statemachine
        :alt: Build status

.. image:: https://codecov.io/gh/fgmacedo/python-statemachine/branch/master/graph/badge.svg
        :target: https://codecov.io/gh/fgmacedo/python-statemachine
        :alt: Coverage report

.. image:: https://readthedocs.org/projects/python-statemachine/badge/?version=latest
        :target: https://python-statemachine.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/fgmacedo/python-statemachine/shield.svg
        :target: https://pyup.io/repos/github/fgmacedo/python-statemachine/
        :alt: Updates

.. image:: https://badges.gitter.im/fgmacedo/python-statemachine.svg
        :alt: Join the chat at https://gitter.im/fgmacedo/python-statemachine
        :target: https://gitter.im/fgmacedo/python-statemachine


Python `finite-state machines <https://en.wikipedia.org/wiki/Finite-state_machine>`_ made easy.


* Free software: MIT license
* Documentation: https://python-statemachine.readthedocs.io.


Getting started
===============

To install Python State Machine, run this command in your terminal:

.. code-block:: console

    $ pip install python-statemachine


Define your state machine:

.. code-block:: python

    from statemachine import StateMachine, State

    class TrafficLightMachine(StateMachine):
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        slowdown = green.to(yellow)
        stop = yellow.to(red)
        go = red.to(green)


You can now create an instance:

>>> traffic_light = TrafficLightMachine()

And inspect about the current state:

>>> traffic_light.current_state
State('Green', identifier='green', value='green', initial=True)
>>> traffic_light.current_state == TrafficLightMachine.green == traffic_light.green
True

For each state, there's a dinamically created property in the form ``is_<state.identifier>``, that
returns ``True`` if the current status matches the query:

>>> traffic_light.is_green
True
>>> traffic_light.is_yellow
False
>>> traffic_light.is_red
False

Query about metadata:

>>> [s.identifier for s in m.states]
['green', 'red', 'yellow']
>>> [t.identifier for t in m.transitions]
['go', 'slowdown', 'stop']

Call a transition:

>>> traffic_light.slowdown()

And check for the current status:

>>> traffic_light.current_state
State('Yellow', identifier='yellow', value='yellow', initial=False)
>>> traffic_light.is_yellow
True

You can't run a transition from an invalid state:

>>> traffic_light.is_yellow
True
>>> traffic_light.slowdown()
Traceback (most recent call last):
...
LookupError: Can't slowdown when in Yellow.

You can also trigger events in an alternative way, calling the ``run(<transition.identificer>)`` method:

>>> traffic_light.is_yellow
True
>>> traffic_light.run('stop')
>>> traffic_light.is_red
True

A state machine can be instantiated with an initial value:

>>> machine = TrafficLightMachine(start_value='red')
>>> traffic_light.is_red
True


Models
------

If you need to persist the current state on another object, or you're using the
state machine to control the flow of another object, you can pass this object
to the ``StateMachine`` constructor:

>>> class MyModel(object):
...     def __init__(self, state):
...         self.state = state
...
>>> obj = MyModel(state='red')
>>> traffic_light = TrafficLightMachine(obj)
>>> traffic_light.is_red
True
>>> obj.state
'red'
>>> obj.state = 'green'
>>> traffic_light.is_green
True
>>> traffic_light.slowdown()
>>> obj.state
'yellow'
>>> traffic_light.is_yellow
True


Callbacks
---------

Callbacks when running events:

.. code-block:: python

    from statemachine import StateMachine, State

    class TrafficLightMachine(StateMachine):
        "A traffic light machine"
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        slowdown = green.to(yellow)
        stop = yellow.to(red)
        go = red.to(green)

        def on_slowdown(self):
            print('Calma, lá!')

        def on_stop(self):
            print('Parou.')

        def on_go(self):
            print('Valendo!')


>>> stm = TrafficLightMachine()
>>> stm.slowdown()
Calma, lá!
>>> stm.stop()
Parou.
>>> stm.go()
Valendo!


Or when entering/exiting states:

.. code-block:: python

    from statemachine import StateMachine, State

    class TrafficLightMachine(StateMachine):
        "A traffic light machine"
        green = State('Green', initial=True)
        yellow = State('Yellow')
        red = State('Red')

        cycle = green.to(yellow) | yellow.to(red) | red.to(green)

        def on_enter_green(self):
            print('Valendo!')

        def on_enter_yellow(self):
            print('Calma, lá!')

        def on_enter_red(self):
            print('Parou.')

>>> stm = TrafficLightMachine()
>>> stm.cycle()
Calma, lá!
>>> stm.cycle()
Parou.
>>> stm.cycle()
Valendo!

Mixins
------

Your model can inherited from a custom mixin to auto-instantiate a state machine.

.. code-block:: python

    class CampaignMachineWithKeys(StateMachine):
        "A workflow machine"
        draft = State('Draft', initial=True, value=1)
        producing = State('Being produced', value=2)
        closed = State('Closed', value=3)

        add_job = draft.to.itself() | producing.to.itself()
        produce = draft.to(producing)
        deliver = producing.to(closed)


    class MyModel(MachineMixin):
        state_machine_name = 'CampaignMachine'

        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            super(MyModel, self).__init__()

        def __repr__(self):
            return "{}({!r})".format(type(self).__name__, self.__dict__)


    model = MyModel(state='draft')
    assert isinstance(model.statemachine, campaign_machine)
    assert model.state == 'draft'
    assert model.statemachine.current_state == model.statemachine.draft
