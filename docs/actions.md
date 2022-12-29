
# Actions


An action is the way a statemachine can cause things to happen in the
outside world, and indeed they are the main reason why they exist at all.
The main point of introducing a state machine is for the
actions to be invoked at the right times, depending on the sequence of events
and the state of the guards.

Actions are most commonly triggered on entry or exit of a state, although
it is possible to place them on an event trigger.

There are several action callbacks that you can define to interact with a
machine in execution.

There are callbacks that you can specify that are generic and will be called
when something changes and are not bounded to a specific state or event:

- `before_transition(event_data)`
- `on_enter_state(event_data)`
- `on_exit_state(event_data)`
- `after_transition(event_data)`

## State

For each defined state, you can register `on_enter_<state>` and `on_exit_<state>` callbacks.

- `on_enter_<state>(event_data)`
- `on_exit_<state>(event_data)`

## Event

For each event trigger, you can register `before_<event>` and `after_<event>`

- `before_<event>(event_data)`
- `after_<event>(event_data)`


## Ordering

Actions will be executed in the following order:

- `before_transition(event_data)`
- `before_<transition>(event_data)`
- `on_enter_state(event_data)`
- `on_enter_<state>(event_data)`
- `on_exit_<state>(event_data)`
- `on_exit_state(event_data)`
- `after_transition(event_data)`
- `after_<transition>(event_data)`


## Example

```{literalinclude} ../tests/examples/traffic_light_machine.py
:language: python
:linenos:
:emphasize-lines: 10
```
