
# Domain models

If you need to use any other object to persist the current state, or you're using the
state machine to control the flow of another object, you can pass this object
to the `StateChart` constructor.

If you don't pass an explicit model instance, this simple `Model` will be used:


```{literalinclude} ../statemachine/model.py
:language: python
:linenos:
```


```{seealso}
See the {ref}`sphx_glr_auto_examples_order_control_rich_model_machine.py` as example of using a
domain object to hold attributes and methods to be used on the `StateChart` definition.
```

```{hint}
Domain models are registered as {ref}`listeners`, so you can have the same level of functionalities
provided to the built-in {ref}`StateChart`, such as implementing all {ref}`actions` and
{ref}`guards` on your domain model and keeping only the definition of {ref}`states` and
{ref}`transitions` on the {ref}`StateChart`.
```

## Typed models

`StateChart` supports a generic type parameter so that type checkers (mypy, pyright) and IDEs
can infer the type of `sm.model` and provide code completion.

Declare your model class and pass it as a type parameter to `StateChart`:

```python
>>> from statemachine import State, StateChart

>>> class OrderModel:
...     order_id: str = ""
...     total: float = 0.0
...     def confirm(self):
...         return f"Order {self.order_id} confirmed: ${self.total}"

>>> class OrderWorkflow(StateChart["OrderModel"]):
...     draft = State(initial=True)
...     confirmed = State(final=True)
...     confirm = draft.to(confirmed, on="on_confirm")
...     def on_confirm(self):
...         return self.model.confirm()

>>> model = OrderModel()
>>> model.order_id = "A-123"
>>> model.total = 49.90
>>> sm = OrderWorkflow(model=model)

>>> sm.send("confirm")
'Order A-123 confirmed: $49.9'

```

With this declaration, `sm.model` is typed as `OrderModel` instead of `Any`, so
`sm.model.order_id`, `sm.model.total`, and `sm.model.confirm()` all get full
autocompletion and type checking in your IDE.

```{note}
When no type parameter is given (e.g. `class MySM(StateChart)`), the model defaults
to `Any`, preserving full backward compatibility.
```
