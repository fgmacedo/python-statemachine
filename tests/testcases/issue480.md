

### Issue 480

A StateMachine that exercises the example given on issue
#[480](https://github.com/fgmacedo/python-statemachine/issues/480).

Should be possible to trigger an event on the initial state activation handler.

```py
>>> from statemachine import StateMachine, State
>>>
>>> class MyStateMachine(StateMachine):
...     State_1 = State(initial=True)
...     State_2 = State(final=True)
...     Trans_1 = State_1.to(State_2)
...
...     def __init__(self):
...         super(MyStateMachine, self).__init__()
...
...     def on_enter_State_1(self):
...         print("Entering State_1 state")
...         self.long_running_task()
...
...     def on_exit_State_1(self):
...         print("Exiting State_1 state")
...
...     def on_enter_State_2(self):
...         print("Entering State_2 state")
...
...     def long_running_task(self):
...         print("long running task process started")
...         self.Trans_1()
...         print("long running task process ended")
...
>>> sm = MyStateMachine()
Entering State_1 state
long running task process started
long running task process ended
Exiting State_1 state
Entering State_2 state

```
