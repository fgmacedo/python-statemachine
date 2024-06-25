
### Issue 449

A StateMachine that exercises the example given on issue
#[449](https://github.com/fgmacedo/python-statemachine/issues/449).



```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...     second = State()
...     third = State()
...     fourth = State()
...     final = State(final=True)
...
...     initial_to_second = initial.to(second)
...     second_to_third = second.to(third)
...     third_to_fourth = third.to(fourth)
...     completion = fourth.to(final)
...
...     def on_enter_state(self, target: State, event: str):
...         print(f"Entering state {target.id}. Event: {event}")
...         if event == "initial_to_second":
...             self.send("second_to_third")
...         if event == "second_to_third":
...             self.send("third_to_fourth")
...         if event == "third_to_fourth":
...             print("third_to_fourth on on_enter_state worked")


```

Exercise:


```py
>>> example = ExampleStateMachine()
Entering state initial. Event: __initial__

>>> print(example.current_state)
Initial

>>> example.send("initial_to_second") # this will call second_to_third and third_to_fourth
Entering state second. Event: initial_to_second
Entering state third. Event: second_to_third
Entering state fourth. Event: third_to_fourth
third_to_fourth on on_enter_state worked

>>> print("My current state is", example.current_state)
My current state is Fourth

```
