
# Domain models

If you need to use any other object to persist the current state, or you're using the
state machine to control the flow of another object, you can pass this object
to the `StateMachine` constructor.

If you don't pass an explicit model instance, this simple `Model` will be used:


```{literalinclude} ../statemachine/model.py
:language: python
:linenos:
```


```{seealso}
See the {ref}`sphx_glr_auto_examples_order_control_rich_model_machine.py` as example of using a
domain object to hold attributes and methods to be used on the `StateMachine` definition.
```

```{hint}
Domain models are registered as {ref}`listeners`, so you can have the same level of functionalities
provided to the built-in {ref}`StateMachine`, such as implementing all {ref}`actions` and
{ref}`guards` on your domain model and keeping only the definition of {ref}`states` and
{ref}`transitions` on the {ref}`StateMachine`.
```
