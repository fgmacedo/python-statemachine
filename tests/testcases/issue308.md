### Issue 308

A StateMachine that exercises the example given on issue
#[308](https://github.com/fgmacedo/python-statemachine/issues/308).

In this example, we share the transition list between events.

```py
>>> from statemachine import StateChart, State

>>> class TestSM(StateChart):
...     state1 = State('s1', initial=True)
...     state2 = State('s2')
...     state3 = State('s3')
...     state4 = State('s4', final=True)
...
...     event1 = state1.to(state2)
...     event2 = state2.to(state3)
...     event3 = state3.to(state4)
...
...     # cycle = state1.to(state2) | state2.to(state3) | state3.to(state4)
...     cycle = event1 | event2 | event3
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
...         print('before event1')
...
...     def on_trans12(self):
...         print('on event1')
...
...     def after_trans12(self):
...         print('after event1')
...
...     def before_trans23(self):
...         print('before event2')
...
...     def on_trans23(self):
...         print('on event2')
...
...     def after_trans23(self):
...         print('after event2')
...
...     def before_trans34(self):
...         print('before event3')
...
...     def on_trans34(self):
...         print('on event3')
...
...     def after_trans34(self):
...         print('after event3')
...

```

Example given:

```py

>>> m = TestSM()
enter state1

>>> m.state1.is_active, m.state2.is_active, m.state3.is_active, m.state4.is_active, list(m.configuration_values)
(True, False, False, False, ['state1'])

>>> _ = m.cycle()
before cycle
exit state1
on cycle
enter state2
after cycle

>>> m.state1.is_active, m.state2.is_active, m.state3.is_active, m.state4.is_active, list(m.configuration_values)
(False, True, False, False, ['state2'])

>>> _ = m.cycle()
before cycle
exit state2
on cycle
enter state3
after cycle

>>> m.state1.is_active, m.state2.is_active, m.state3.is_active, m.state4.is_active, list(m.configuration_values)
(False, False, True, False, ['state3'])

>>> _ = m.cycle()
before cycle
exit state3
on cycle
enter state4
after cycle

>>> m.state1.is_active, m.state2.is_active, m.state3.is_active, m.state4.is_active, list(m.configuration_values)
(False, False, False, True, ['state4'])

```
