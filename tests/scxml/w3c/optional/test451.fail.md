# Testcase: test451

InvalidDefinition: The state machine has a definition error

Final configuration: `No configuration`

---

## Logs
```py
No logs
```

## "On transition" events
```py
No events
```

## Traceback
```py
Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 114, in _add
    sc_class = create_machine_class_from_definition(location, **definition)
  File "/home/macedo/projects/python-statemachine/statemachine/io/__init__.py", line 140, in create_machine_class_from_definition
    return StateMachineMetaclass(name, (StateMachine,), attrs_mapper)  # type: ignore[return-value]
  File "/home/macedo/projects/python-statemachine/statemachine/factory.py", line 76, in __init__
    cls._check()
    ~~~~~~~~~~^^
  File "/home/macedo/projects/python-statemachine/statemachine/factory.py", line 121, in _check
    cls._check_disconnected_state()
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
  File "/home/macedo/projects/python-statemachine/statemachine/factory.py", line 190, in _check_disconnected_state
    raise InvalidDefinition(
    ...<5 lines>...
    )
statemachine.exceptions.InvalidDefinition: There are unreachable states. The statemachine graph should have a single component. Disconnected states: ['fail', 'pass']

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/macedo/projects/python-statemachine/tests/scxml/test_scxml_cases.py", line 114, in test_scxml_usecase
    processor.parse_scxml_file(testcase_path)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 30, in parse_scxml_file
    return self.parse_scxml(path.stem, scxml_content)
           ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 34, in parse_scxml
    self.process_definition(definition, location=sm_name)
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 49, in process_definition
    self._add(location, {"states": states_dict})
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 118, in _add
    raise InvalidDefinition(
        f"Failed to create state machine class: {e} from definition: {definition}"
    ) from e
statemachine.exceptions.InvalidDefinition: Failed to create state machine class: There are unreachable states. The statemachine graph should have a single component. Disconnected states: ['fail', 'pass'] from definition: {'states': {'p': {'initial': True, 'parallel': True, 'states': [State('S0', id='s0', value='s0', initial=True, final=False, parallel=False), State('S1', id='s1', value='s1', initial=True, final=False, parallel=False)]}, 'pass': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'pass'")]))]}, 'fail': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'fail'")]))]}}}

```
