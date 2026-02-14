# API

## StateChart

```{versionadded} 3.0.0
```

```{eval-rst}
.. autoclass:: statemachine.statemachine.StateChart
    :members:
    :undoc-members:
```

## StateMachine

```{eval-rst}
.. autoclass:: statemachine.statemachine.StateMachine
    :members:
    :undoc-members:
```

## State

```{seealso}
{ref}`States` reference.
```


```{eval-rst}
.. autoclass:: statemachine.state.State
    :members:
```

## HistoryState

```{versionadded} 3.0.0
```

```{eval-rst}
.. autoclass:: statemachine.state.HistoryState
    :members:
```

## States (class)

```{eval-rst}
.. autoclass:: statemachine.states.States
    :noindex:
    :members:
```

## Transition

```{seealso}
{ref}`Transitions` reference.
```

```{eval-rst}
.. autoclass:: statemachine.transition.Transition
    :members:
```

## TransitionList

```{eval-rst}
.. autoclass:: statemachine.transition_list.TransitionList
    :members:
```

## Model

```{seealso}
{ref}`Domain models` reference.
```


```{eval-rst}
.. autoclass:: statemachine.model.Model
    :members:
```

## TriggerData


```{eval-rst}
.. autoclass:: statemachine.event_data.TriggerData
    :members:
```

## Event

```{eval-rst}
.. autoclass:: statemachine.event.Event
    :members: id, name, __call__
```

## EventData

```{eval-rst}
.. autoclass:: statemachine.event_data.EventData
    :members:
```

## Callback conventions

These are convention-based callbacks that you can define on your state machine
subclass. They are not methods on the base class — define them in your subclass
to enable the behavior.

### `prepare_event`

Called before every event is processed. Returns a `dict` of keyword arguments
that will be merged into `**kwargs` for all subsequent callbacks (guards, actions,
entry/exit handlers) during that event's processing:

```python
class MyMachine(StateChart):
    initial = State(initial=True)
    loop = initial.to.itself()

    def prepare_event(self):
        return {"request_id": generate_id()}

    def on_loop(self, request_id):
        # request_id is available here
        ...
```

## create_machine_class_from_definition

```{versionadded} 3.0.0
```

```{eval-rst}
.. autofunction:: statemachine.io.create_machine_class_from_definition
```
