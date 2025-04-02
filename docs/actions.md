# Actions

Action is the way a {ref}`StateMachine` can cause things to happen in the
outside world, and indeed they are the main reason why they exist at all.

The main point of introducing a state machine is for the
actions to be invoked at the right times, depending on the sequence of events
and the state of the {ref}`conditions`.

Actions are most commonly performed on entry or exit of a state, although
it is possible to add them before/after a transition.

There are several action callbacks that you can define to interact with a
StateMachine in execution.

There are callbacks that you can specify that are generic and will be called
when something changes, and are not bound to a specific state or event:

- `before_transition()`

- `on_exit_state()`

- `on_transition()`

- `on_enter_state()`

- `after_transition()`

The following example offers an overview of the "generic" callbacks available:

```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...     final = State(final=True)
...
...     loop = initial.to.itself()
...     go = initial.to(final)
...
...     def before_transition(self, event, state):
...         print(f"Before '{event}', on the '{state.id}' state.")
...         return "before_transition_return"
...
...     def on_transition(self, event, state):
...         print(f"On '{event}', on the '{state.id}' state.")
...         return "on_transition_return"
...
...     def on_exit_state(self, event, state):
...         print(f"Exiting '{state.id}' state from '{event}' event.")
...
...     def on_enter_state(self, event, state):
...         print(f"Entering '{state.id}' state from '{event}' event.")
...
...     def after_transition(self, event, state):
...         print(f"After '{event}', on the '{state.id}' state.")


>>> sm = ExampleStateMachine()  # On initialization, the machine run a special event `__initial__`
Entering 'initial' state from '__initial__' event.

>>> sm.loop()
Before 'loop', on the 'initial' state.
Exiting 'initial' state from 'loop' event.
On 'loop', on the 'initial' state.
Entering 'initial' state from 'loop' event.
After 'loop', on the 'initial' state.
['before_transition_return', 'on_transition_return']

>>> sm.go()
Before 'go', on the 'initial' state.
Exiting 'initial' state from 'go' event.
On 'go', on the 'initial' state.
Entering 'final' state from 'go' event.
After 'go', on the 'final' state.
['before_transition_return', 'on_transition_return']

```


```{seealso}
All actions and {ref}`conditions` support multiple method signatures. They follow the
{ref}`dynamic-dispatch` method calling implemented on this library.
```

## State actions

For each defined {ref}`state`, you can declare `enter` and `exit` callbacks.

### Bind state actions by naming convention

Callbacks by naming convention will be searched on the StateMachine and on the
model, using the patterns:

- `on_enter_<state.id>()`

- `on_exit_<state.id>()`


```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself()
...
...     def on_enter_initial(self):
...         pass
...
...     def on_exit_initial(self):
...         pass

```

### Bind state actions using params

Use the `enter` or `exit` params available on the `State` constructor.

```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True, enter="entering_initial", exit="leaving_initial")
...
...     loop = initial.to.itself()
...
...     def entering_initial(self):
...         pass
...
...     def leaving_initial(self):
...         pass

```

```{hint}
It's also possible to use an event name as action.
```

### Bind state actions using decorator syntax


```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself()
...
...     @initial.enter
...     def entering_initial(self):
...         pass
...
...     @initial.exit
...     def leaving_initial(self):
...         pass

```

## Transition actions

For each {ref}`events`, you can register `before`, `on`, and `after` callbacks.

### Declare transition actions by naming convention

The action will be registered for every {ref}`transition` associated with the event.

Callbacks by naming convention will be searched on the StateMachine and the model,
using the patterns:

- `before_<event>()`

- `on_<event>()`

- `after_<event>()`


```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself()
...
...     def before_loop(self):
...         pass
...
...     def on_loop(self):
...         pass
...
...     def after_loop(self):
...         pass
...

```

### Bind transition actions using params

```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself(before="just_before", on="its_happening", after="loop_completed")
...
...     def just_before(self):
...         pass
...
...     def its_happening(self):
...         pass
...
...     def loop_completed(self):
...         pass

```

```{hint}
It's also possible to use an event name as action to chain transitions.
```

### Bind transition actions using decorator syntax

The action will be registered for every {ref}`transition` in the list associated with the event.


```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself()
...
...     @loop.before
...     def just_before(self):
...         pass
...
...     @loop.on
...     def its_happening(self):
...         pass
...
...     @loop.after
...     def loop_completed(self):
...         pass
...
...     @loop.cond
...     def should_we_allow_loop(self):
...         return True
...
...     @loop.unless
...     def should_we_block_loop(self):
...         return False

```

### Declare an event while also giving an "on" action using the decorator syntax

You can also declare an event while also adding a callback:

```py
>>> from statemachine import StateMachine, State

>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     @initial.to.itself()
...     def loop(self):
...         print("On loop")
...         return 42

```

Note that with this syntax, the resulting `loop` that is present on the `ExampleStateMachine.loop`
namespace is not a simple method, but an {ref}`event` trigger. So it only executes if the
StateMachine is in the right state.

So, you can use the event-oriented approach:

```py
>>> sm = ExampleStateMachine()

>>> sm.send("loop")
On loop
42

```


## Other callbacks

In addition to {ref}`actions`, you can specify {ref}`validators and guards` that are checked before a transition is started. They are meant to stop a transition to occur.

```{seealso}
See {ref}`conditions` and {ref}`validators`.
```


## Ordering

There are major groups of callbacks, these groups run sequentially.

```{warning}
Actions registered on the same group don't have order guaranties and are executed in parallel when using the {ref}`AsyncEngine`, and may be executed in parallel in future versions of {ref}`SyncEngine`.
```


```{list-table}
:header-rows: 1

*   - Group
    - Action
    - Current state
    - Description
*   - Validators
    - `validators()`
    - `source`
    - Validators raise exceptions.
*   - Conditions
    - `cond()`, `unless()`
    - `source`
    - Conditions are predicates that prevent transitions to occur.
*   - Before
    - `before_transition()`, `before_<event>()`
    - `source`
    - Callbacks declared in the transition or event.
*   - Exit
    - `on_exit_state()`, `on_exit_<state.id>()`
    - `source`
    - Callbacks declared in the source state.
*   - On
    - `on_transition()`, `on_<event>()`
    - `source`
    - Callbacks declared in the transition or event.
*   - **State updated**
    -
    -
    - Current state is updated.
*   - Enter
    - `on_enter_state()`, `on_enter_<state.id>()`
    - `destination`
    - Callbacks declared in the destination state.
*   - After
    - `after_<event>()`, `after_transition()`
    - `destination`
    - Callbacks declared in the transition or event.

```


## Return values

Currently only certain actions' return values will be combined as a list and returned for
a triggered transition:

- `before_transition()`

- `before_<event>()`

- `on_transition()`

- `on_<event>()`

Note that `None` will be used if the action callback does not return anything, but only when it is
defined explicitly. The following provides an example:

```py
>>> class ExampleStateMachine(StateMachine):
...     initial = State(initial=True)
...
...     loop = initial.to.itself()
...
...     def before_loop(self):
...         return "Before loop"
...
...     def on_transition(self):
...         pass
...
...     def on_loop(self):
...         return "On loop"
...

>>> sm = ExampleStateMachine()

>>> sm.loop()
['Before loop', None, 'On loop']

```

For {ref}`RTC model`, only the main event will get its value list, while the chained ones simply get
`None` returned. For {ref}`Non-RTC model`, results for every event will always be collected and returned.


(dynamic-dispatch)=
(dynamic dispatch)=
## Dependency injection

{ref}`statemachine` implements a dependency injection mechanism on all available {ref}`Actions` and
{ref}`Conditions` that automatically inspects and matches the expected callback params with those available by the library in conjunction with any values informed when calling an event using `*args` and `**kwargs`.

The library ensures that your method signatures match the expected arguments.

For example, if you need to access the source (state), the event (event), or any keyword arguments passed with the trigger in any method, simply include these parameters in the method. They will be automatically passed by the dependency injection dispatch mechanics.

In other words, if you implement a method to handle an event and don't declare any parameter,
you'll be fine, if you declare an expected parameter, you'll also be covered.

For your convenience, all these parameters are available for you on any callback:


`*args`
: All positional arguments provided on the {ref}`Event`.

`**kwargs`
: All keyword arguments provided on the {ref}`Event`.

`event_data`
: A reference to {ref}`EventData` instance.

`event`
: The {ref}`Event` that was triggered.

`source`
: The {ref}`State` the state machine was in when the {ref}`Event` started.

`state`
: The current {ref}`State` of the state machine.

`target`
: The destination {ref}`State` of the transition.

`model`
: A reference to the underlying model that holds the current {ref}`State`.

`transition`
: The {ref}`Transition` instance that was activated by the {ref}`Event`.


So, you can implement Actions and Guards like these, but this list is not exhaustive, it's only
to give you a few examples...  any combination of parameters will work, including extra parameters
that you may inform when triggering an {ref}`event`:

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

```{seealso}
See the example {ref}`sphx_glr_auto_examples_all_actions_machine.py` for a complete example of
order resolution of callbacks.
```
