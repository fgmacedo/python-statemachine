(validators-and-guards)=
# Validators and guards

Validations and Guards are checked before an transition is started. They are meant to stop a
transition to occur.

The main difference, is that {ref}`validators` raise exceptions to stop the flow, and {ref}`guards`
act like predicates that should resolve for a ``boolean`` value.

```{seealso}
Please see {ref}`dynamic-dispatch` to know more about how this lib supports multiple signatures
for all the available callbacks, being validators and guards or {ref}`actions`.
```

## Guards

Also known as **Conditional transition**.

A guard is a condition that may be checked when a statemachine wants to handle
an {ref}`event`. A guard is declared on the {ref}`transition`, and when that transition
would trigger, then the guard (if any) is checked.  If the guard is `True`
then the transition does happen. If the guard is `False`, the transition
is ignored.

When transitions have guards, then it's possible to define two or more
transitions for the same event from the same {ref}`state`, i.e. that a state has
two (or more) transitions for the same event.  When the event happens, then
the guarded transitions are checked, one by one, and the first transition
whose guard is true will be used, the others will be ignored.

A guard is generally a boolean function or boolean variable and must not have any side effects.
Side effects are reserved for {ref}`actions`.

There are two variations of Guard clauses available:


cond
: A list of conditions, acting like predicates. A transition is only allowed to occur if
all conditions evaluate to ``True``.

unless
: Same as `cond`, but the transition is allowed if all conditions evaluate to `False`.

```{hint}
In Python, a boolean value is either `True` or `False`. However, there are also specific values that
are considered "**falsy**" and will evaluate as `False` when used in a boolean context.

These include:

1. The special value `None`.
1. Numeric values of `0` or `0.0`.
1. **Empty** strings, lists, tuples, sets, and dictionaries.
1. Instances of certain classes that define a `__bool__()` or `__len__()` method that returns
   `False` or `0`, respectively.

On the other hand, any value that is not considered "**falsy**" is considered "**truthy**" and will evaluate to `True` when used in a boolean context.

So, a condition `s1.to(s2, cond=lambda: [])` will evaluate as `False`, as an empty list is a
**falsy** value.
```

## Validators


Are like {ref}`guards`, but instead of evaluating to boolean, they are expected to raise an
exception to stop the flow. It may be useful for imperative style programming when you don't
wanna to continue evaluating other possible transitions and exit immediately.


Consider this example:

```py

class InvoiceStateMachine(StateMachine):
    unpaid = State("unpaid", initial=True)
    paid = State("paid")
    failed = State("failed")

    pay = (
        unpaid.to(paid, cond="payment_success")
        | failed.to(paid)
        | unpaid.to(failed)
    )

    def payment_success(self, event_data):
        return <validation logic goes here>

```


Reference: [Statecharts](https://statecharts.dev/).
