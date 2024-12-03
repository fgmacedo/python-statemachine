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
: A list of condition expressions, acting like predicates. A transition is only allowed to occur if
all conditions evaluate to ``True``.
* Single condition expression: `cond="condition"` / `cond="<condition expression>"`
* Multiple condition expressions: `cond=["condition1", "condition2"]`

unless
: Same as `cond`, but the transition is only allowed if all conditions evaluate to ``False``.
* Single condition: `unless="condition"` / `unless="<condition expression>"`
* Multiple conditions: `unless=["condition1", "condition2"]`

### Condition expressions

This library supports a mini-language for boolean expressions in conditions, allowing the definition of guards that control transitions based on specified criteria. It includes basic [boolean algebra](https://en.wikipedia.org/wiki/Boolean_algebra) operators, parentheses for controlling precedence, and **names** that refer to attributes on the state machine, its associated model, or registered {ref}`Listeners`.

```{tip}
All condition expressions are evaluated when the State Machine is instantiated. This is by design to help you catch any invalid definitions early, rather than when your state machine is running.
```

The mini-language is based on Python's built-in language and the [`ast`](https://docs.python.org/3/library/ast.html) parser, so there are no surprises if you’re familiar with Python. Below is a formal specification to clarify the structure.

#### Syntax elements

1. **Names**:
   - Names refer to attributes on the state machine instance, its model or listeners, used directly in expressions to evaluate conditions.
   - Names must consist of alphanumeric characters and underscores (`_`) and cannot begin with a digit (e.g., `is_active`, `count`, `has_permission`).
   - Any property name used in the expression must exist as an attribute on the state machine, model instance, or listeners, otherwise, an `InvalidDefinition` error is raised.
   - Names can be pointed to `properties`, `attributes` or `methods`. If pointed to `attributes`, the library will create a
     wrapper get method so each time the expression is evaluated the current value will be retrieved.

2. **Boolean operators and precedence**:
   - The following Boolean operators are supported, listed from highest to lowest precedence:
     1. `not` / `!` — Logical negation
     2. `and` / `^` — Logical conjunction
     3. `or` / `v` — Logical disjunction
     4. `or` / `v` — Logical disjunction
   - These operators are case-sensitive (e.g., `NOT` and `Not` are not equivalent to `not` and will raise syntax errors).
   - Both formats can be used interchangeably, so `!sauron_alive` and `not sauron_alive` are equivalent.

2. **Comparisson operators**:
   - The following comparison operators are supported:
     1. `>` — Greather than.
     2. `>=` — Greather than or equal.
     3. `==` — Equal.
     4. `!=` — Not equal.
     5. `<` — Lower than.
     6. `<=` — Lower than or equal.
   - All comparison operations in Python have the same priority.

3. **Parentheses for precedence**:
   - When operators with the same precedence appear in the expression, evaluation proceeds from left to right, unless parentheses specify a different order.
   - Parentheses `(` and `)` are supported to control the order of evaluation in expressions.
   - Expressions within parentheses are evaluated first, allowing explicit precedence control (e.g., `(is_admin or is_moderator) and has_permission`).

#### Expression Examples

Examples of valid boolean expressions include:
- `is_logged_in and has_permission`
- `not is_active or is_admin`
- `!(is_guest ^ has_access)`
- `(is_admin or is_moderator) and !is_banned`
- `has_account and (verified or trusted)`
- `frodo_has_ring and gandalf_present or !sauron_alive`

Being used on a transition definition:

```python
start.to(end, cond="frodo_has_ring and gandalf_present or !sauron_alive")
```


```{seealso}
See {ref}`sphx_glr_auto_examples_lor_machine.py` for an example of
using boolean algebra in conditions.
```

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
