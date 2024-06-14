### Issue 417

A StateMachine that exercises the derived example given on issue
#[417](https://github.com/fgmacedo/python-statemachine/issues/417).

In this example, the condition callback must be registered using a method by reference, not by it's name.
Just to be sure, we've added a lot of variations.

```py
>>> from statemachine import State
>>> from statemachine import StateMachine

>>> class Model:
...     def __init__(self, counter: int = 0):
...         self.state = None
...         self.counter = counter
...
...     def can_be_started_on_model(self) -> bool:
...         return self.counter > 0
...
...     @property
...     def can_be_started_as_property_on_model(self) -> bool:
...         return self.counter > 1
...
...     @property
...     def can_be_started_as_property_str_on_model(self) -> bool:
...         return self.counter > 2

>>> class ExampleStateMachine(StateMachine):
...     created = State(initial=True)
...     started = State(final=True)
...
...     def can_be_started(self) -> bool:
...         return self.counter > 0
...
...     @property
...     def can_be_started_as_property(self) -> bool:
...         return self.counter > 1
...
...     @property
...     def can_be_started_as_property_str(self) -> bool:
...         return self.counter > 2
...
...     start = created.to(
...          started,
...          cond=[
...              can_be_started, can_be_started_as_property, "can_be_started_as_property_str",
...              Model.can_be_started_on_model, Model.can_be_started_as_property_on_model,
...              "can_be_started_as_property_str_on_model"
...          ]
...     )
...
...     def __init__(self, model=None, counter: int = 0):
...         self.counter = counter
...         super().__init__(model=model)
...
...     def on_start(self):
...         print("started")
...

>>> def test_machine(counter):
...     model = Model(counter)
...     sm = ExampleStateMachine(model, counter)
...     sm.start()

```

Expected output:

```py
>>> test_machine(0)
Traceback (most recent call last):
...
statemachine.exceptions.TransitionNotAllowed: Can't start when in Created.

>>> test_machine(3)
started

```

## Invalid scenarios

Should raise an exception if the property is not found on the correct objects:


```py

>>> class StrangeObject:
...     @property
...     def this_cannot_resolve(self) -> bool:
...         return True



>>> class ExampleStateMachine(StateMachine):
...     created = State(initial=True)
...     started = State(final=True)
...
...     start = created.to(
...          started,
...          cond=[StrangeObject.this_cannot_resolve]
...     )
...

>>> def test_machine():
...     sm = ExampleStateMachine()
...     sm.start()

```

Expected output:

```py
>>> test_machine()
Traceback (most recent call last):
...
statemachine.exceptions.InvalidDefinition: Error on transition start from Created to Started when resolving callbacks: Did not found name ... from model or statemachine
```
