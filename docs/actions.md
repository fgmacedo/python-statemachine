(actions)=

# Actions


An action is the way a statemachine can cause things to happen in the
outside world, and indeed they are the main reason why they exist at all.
The main point of introducing a state machine is for the
actions to be invoked at the right times, depending on the sequence of events
and the state of the guards.

Actions are most commonly performed on entry or exit of a state, although
it is possible to add them before / after a transition.

There are several action callbacks that you can define to interact with a
machine in execution.

There are callbacks that you can specify that are generic and will be called
when something changes and are not bounded to a specific state or event:

- `before_transition(event_data)`

- `on_enter_state(event_data)`

- `on_exit_state(event_data)`

- `after_transition(event_data)`

## State actions

For each defined state, you can register `on_enter_<state>` and `on_exit_<state>` callbacks.

- `on_enter_<state_identifier>(event_data)`

- `on_exit_<state_identifier>(event_data)`

## Event actions

For each event, you can register `before_<event>` and `after_<event>`

- `before_<event>(event_data)`

- `after_<event>(event_data)`


(validators-and-guards)=

## Other callbacks

In addition to {ref}`actions`, you can specify {ref}`validators-and-guards` that are checked
before an transition is started. They are meant to stop a transition to occur.

```{seealso}
See {ref}`guards` and {ref}`validators`.
```


## Ordering

Actions and Guards will be executed in the following order:

- `validators(event_data)`  (attached to the transition)

- `conditions(event_data)`  (attached to the transition)

- `unless(event_data)`  (attached to the transition)

- `before_transition(event_data)`

- `before_<event>(event_data)`

- `on_exit_state(event_data)`

- `on_exit_<state_identifier>(event_data)`

- `on_enter_state(event_data)`

- `on_enter_<state_identifier>(event_data)`

- `after_<event>(event_data)`

- `after_transition(event_data)`


## Dynamic dispatch

python-statemachine implements a custom dispatch mechanism on all those available Actions and
Guards, this means that you can declare an arbitrary number of `*args` and `**kwargs`, and the
library will to it's best to match your method signature of what's expect to receive with the
provided arguments.

In other words, if you implement a method to handle an event and don't declare any parameter,
you'll be fine, if you declare an expected parameter, you'll also be covered.

For your convenience, all these parameters are available for you on any Action or Guard:

- `*args`: All positional arguments provided on the {ref}`Event`.

- `**kwargs`: All keyword arguments provided on the {ref}`Event`.

- `event_data`: A reference to `EventData` instance.

- `event`: The {ref}`Event` that was triggered.

- `source`: The {ref}`State` the statemachine was when the {ref}`Event` started.

- `state`: The current {ref}`State` of the statemachine.

- `model`: A reference to the underlying model that holds the current {ref}`State`.

- `transition`: The {ref}`Transition` instance that was activated by the {ref}`Event`.

So, you can implement Actions and Guards like these:

```py
def action_or_guard_method_name(self):
    pass

def action_or_guard_method_name(self, model):
    pass

def action_or_guard_method_name(self, event):
    pass

def action_or_guard_method_name(self, *args, event_data, event, source, state, model, **kwargs):
    pass

```


## Example

See this test for a complete example of order resolution of callbacks.

```{literalinclude} ../tests/test_actions.py
:language: python
:linenos:
```
