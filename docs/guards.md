(validators-and-guards)=
(validators and guards)=
# Conditions and Validators

Conditions and Validations are checked before a transition is started. They are meant to prevent or stop a
transition to occur.

The main difference is that {ref}`validators` raise exceptions to stop the flow, and {ref}`conditions`
act like predicates that shall resolve to a ``boolean`` value.

```{seealso}
Please see {ref}`dynamic-dispatch` to know more about how this lib supports multiple signatures
for all the available callbacks, being validators and guards or {ref}`actions`.
```

(guards)=
## Conditions

This feature is also known as a **Conditional Transition**.

A conditional transition occurs only if specific conditions or criteria are met. In addition to checking if there is a transition handling the event in the current state, you can register callbacks that are evaluated based on other factors or inputs at runtime.

When a transition is conditional, it includes a condition (also known as a _guard_) that must be satisfied for the transition to take place. If the condition is not met, the transition does not occur, and the state machine remains in its current state or follows an alternative path.

This feature allows for multiple transitions on the same {ref}`event`, with each {ref}`transition` checked in the order they are declared. A condition acts like a predicate (a function that evaluates to true/false) and is checked when a {ref}`statemachine` handles an {ref}`event` with a transition from the current state bound to this event. The first transition that meets the conditions (if any) is executed. If none of the transitions meet the conditions, the state machine either raises an exception or does nothing (see the `allow_event_without_transition` parameter of {ref}`StateMachine`).

When {ref}`transitions` have guards, it is possible to define two or more transitions for the same {ref}`event` from the same {ref}`state`. When the {ref}`event` occurs, the guarded transitions are checked one by one, and the first transition whose guard is true will be executed, while the others will be ignored.

A condition is generally a boolean function, property, or attribute, and must not have any side effects. Side effects are reserved for {ref}`actions`.

There are two variations of Guard clauses available:


cond
: A list of conditions, acting like predicates. A transition is only allowed to occur if
all conditions evaluate to ``True``.
* Single condition: `cond="condition"`
* Multiple conditions: `cond=["condition1", "condition2"]`

unless
: Same as `cond`, but the transition is only allowed if all conditions evaluate to ``False``.
* Single condition: `unless="condition"`
* Multiple conditions: `unless=["condition1", "condition2"]`

```{seealso}
See {ref}`sphx_glr_auto_examples_air_conditioner_machine.py` for an example of
combining multiple transitions to the same event.
```

```{hint}
In Python, a boolean value is either `True` or `False`. However, there are also specific values that
are considered "**falsy**" and will evaluate as `False` when used in a boolean context.

These include:

1. The special value `None`.
2. Numeric values of `0` or `0.0`.
3. **Empty** strings, lists, tuples, sets, and dictionaries.
4. Instances of certain classes that define a `__bool__()` or `__len__()` method that returns
   `False` or `0`, respectively.

On the other hand, any value that is not considered "**falsy**" is considered "**truthy**" and will evaluate to `True` when used in a boolean context.

So, a condition `s1.to(s2, cond=lambda: [])` will evaluate as `False`, as an empty list is a
**falsy** value.
```

## Validators


Are like {ref}`guards`, but instead of evaluating to boolean, they are expected to raise an
exception to stop the flow. It may be useful for imperative-style programming when you don't
want to continue evaluating other possible transitions and exit immediately.

* Single validator: `validators="validator"`
* Multiple validator: `validators=["validator1", "validator2"]`

Both conditions and validators can also be combined for a single event.

    <event> = <state1>.to(<state2>, cond="condition1", unless="condition2", validators="validator")

Consider this example:

```py

class InvoiceStateMachine(StateMachine):
    unpaid = State(initial=True)
    paid = State()
    failed = State()

    paused = False
    offer_valid = True

    pay = (
        unpaid.to(paid, cond="payment_success") |
        unpaid.to(failed, validators="validator", unless="paused") |
        failed.to(paid, cond=["payment_success", "offer_valid"])
    )
    def payment_success(self, event_data):
        return <condition logic goes here>

    def validator(self):
        return <validator logic goes here>
```
```{seealso}
See the example {ref}`sphx_glr_auto_examples_all_actions_machine.py` for a complete example of
validators and guards.
```

Reference: [Statecharts](https://statecharts.dev/).
