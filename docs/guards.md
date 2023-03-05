(validators-and-guards)=
# Validators and guards

Validations and Guards are checked before a transition is started. They are meant to stop a
transition to occur.

The main difference is that {ref}`validators` raise exceptions to stop the flow, and {ref}`guards`
act like predicates that shall resolve to a ``boolean`` value.

```{seealso}
Please see {ref}`dynamic-dispatch` to know more about how this lib supports multiple signatures
for all the available callbacks, being validators and guards or {ref}`actions`.
```

## Guards

Also known as **Conditional transition**.

A guard is a condition that may be checked when a {ref}`statemachine` wants to handle
an {ref}`event`. A guard is declared on the {ref}`transition`, and when that {ref}`transition`
would trigger, then the guard (if any) is checked. If the guard is `True`
then the transition does happen. If the guard is `False`, the transition
is ignored.

When {ref}`transitions` have guards, then it's possible to define two or more
transitions for the same {ref}`event` from the same {ref}`state`. When the {ref}`event` happens, then
the guarded transitions are checked, one by one, and the first transition
whose guard is true will be used, and the others will be ignored.

A guard is generally a boolean function or boolean variable and must not have any side effects.
Side effects are reserved for {ref}`actions`.

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
