# Testcase: test580

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
statemachine.exceptions.InvalidDefinition: Failed to create state machine class: 'sh1' from definition: {'states': {'p1': {'initial': True, 'parallel': True, 'enter': [<function create_datamodel_action_callable.<locals>.datamodel at 0x7f91ef9b1620>, ExecuteBlock(ExecutableContent(actions=[SendAction(event='timeout', eventexpr=None, target=None, type=None, id=None, idlocation=None, delay='2s', delayexpr=None, namelist=None, params=[], content=None)]))], 'states': [State('S0', id='s0', value='s0', initial=False, final=False), State('S1', id='s1', value='s1', initial=False, final=False)]}, 'pass': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'pass'")]))]}, 'fail': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'fail'")]))]}}}

```
