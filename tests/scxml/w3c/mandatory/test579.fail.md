# Testcase: test579

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
  File "/home/macedo/projects/python-statemachine/statemachine/io/__init__.py", line 115, in create_machine_class_from_definition
    target = states_instances[transition_data["target"]]
             ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
KeyError: 'sh1'

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
statemachine.exceptions.InvalidDefinition: Failed to create state machine class: 'sh1' from definition: {'states': {'s0': {'initial': True, 'enter': [<function create_datamodel_action_callable.<locals>.datamodel at 0x7f3c5f1fe2a0>, ExecuteBlock(ExecutableContent(actions=[SendAction(event='timeout', eventexpr=None, target=None, type=None, id=None, idlocation=None, delay=None, delayexpr="'1s'", namelist=None, params=[], content=None), RaiseAction(event='event1')]))], 'exit': [ExecuteBlock(ExecutableContent(actions=[AssignAction(location='Var1', expr='Var1 + 1')]))], 'states': [State('S01', id='s01', value='s01', initial=False, final=False), State('S02', id='s02', value='s02', initial=False, final=False), State('S03', id='s03', value='s03', initial=False, final=False)]}, 's2': {}, 's3': {}, 'pass': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'pass'")]))]}, 'fail': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'fail'")]))]}}}

```
