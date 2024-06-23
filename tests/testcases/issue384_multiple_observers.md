### Issue 384

A StateMachine that exercises the example given on issue
#[384](https://github.com/fgmacedo/python-statemachine/issues/384).

In this example, we register multiple observers to the same named callback.

This works also as a regression test.

```py
>>> from statemachine import State
>>> from statemachine import StateMachine

>>> class MyObs:
...     def on_move_car(self):
...         print("I observed moving from 1")

>>> class MyObs2:
...     def on_move_car(self):
...         print("I observed moving from 2")
...


>>> class Car(StateMachine):
...     stopped = State(initial=True)
...     moving = State()
...
...     move_car = stopped.to(moving)
...     stop_car = moving.to(stopped)
...
...     def on_move_car(self):
...         print("I'm moving")

```

Running:

```py
>>> car = Car()
>>> obs = MyObs()
>>> obs2 = MyObs2()
>>> car.add_listener(obs)
Car(model=Model(state=stopped), state_field='state', current_state='stopped')

>>> car.add_listener(obs2)
Car(model=Model(state=stopped), state_field='state', current_state='stopped')

>>> car.add_listener(obs2)  # test to not register duplicated observer callbacks
Car(model=Model(state=stopped), state_field='state', current_state='stopped')

>>> car.move_car()
I'm moving
I observed moving from 1
I observed moving from 2
[None, None, None]

```
