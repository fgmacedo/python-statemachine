### Issue 308

A StateMachine that exercices the example given on issue
#[308](https://github.com/fgmacedo/python-statemachine/issues/308).

On this example, we share the transitions list between events.

```py
>>> from statemachine import StateMachine, State

>>> class TestSM(StateMachine):
...     state1 = State('s1', initial=True)
...     state2 = State('s2')
...     state3 = State('s3')
...     state4 = State('s4', final=True)
...
...     trans12 = state1.to(state2)
...     trans23 = state2.to(state3)
...     trans34 = state3.to(state4)
...
...     # cycle = state1.to(state2) | state2.to(state3) | state3.to(state4)
...     cycle = trans12 | trans23 | trans34
...
...     def before_cycle(self):
...         print("before cycle")
...
...     def on_cycle(self):
...         print("on cycle")
...
...     def after_cycle(self):
...         print("after cycle")
...
...     def on_enter_state1(self):
...         print('enter state1')
...
...     def on_exit_state1(self):
...         print('exit state1')
...
...     def on_enter_state2(self):
...         print('enter state2')
...
...     def on_exit_state2(self):
...         print('exit state2')
...
...     def on_enter_state3(self):
...         print('enter state3')
...
...     def on_exit_state3(self):
...         print('exit state3')
...
...     def on_enter_state4(self):
...         print('enter state4')
...
...     def on_exit_state4(self):
...         print('exit state4')
...
...     def before_trans12(self):
...         print('before trans12')
...
...     def on_trans12(self):
...         print('on trans12')
...
...     def after_trans12(self):
...         print('after trans12')
...
...     def before_trans23(self):
...         print('before trans23')
...
...     def on_trans23(self):
...         print('on trans23')
...
...     def after_trans23(self):
...         print('after trans23')
...
...     def before_trans34(self):
...         print('before trans34')
...
...     def on_trans34(self):
...         print('on trans34')
...
...     def after_trans34(self):
...         print('after trans34')
...

```

Example given:

```py

>>> m = TestSM()
enter state1

>>> m.is_state1, m.is_state2, m.is_state3, m.is_state4, m.current_state ; _ = m.cycle()
(True, False, False, False, State('s1', id='state1', value='state1', initial=True, final=False))
before cycle
before trans12
exit state1
on cycle
on trans12
enter state2
after cycle
after trans12

>>> m.is_state1, m.is_state2, m.is_state3, m.is_state4, m.current_state ; _ = m.cycle()
(False, True, False, False, State('s2', id='state2', value='state2', initial=False, final=False))
before cycle
before trans23
exit state2
on cycle
on trans23
enter state3
after cycle
after trans23

>>> m.is_state1, m.is_state2, m.is_state3, m.is_state4, m.current_state ; _ = m.cycle()
(False, False, True, False, State('s3', id='state3', value='state3', initial=False, final=False))
before cycle
before trans34
exit state3
on cycle
on trans34
enter state4
after cycle
after trans34

>>> m.is_state1, m.is_state2, m.is_state3, m.is_state4, m.current_state
(False, False, False, True, State('s4', id='state4', value='state4', initial=False, final=True))

```
