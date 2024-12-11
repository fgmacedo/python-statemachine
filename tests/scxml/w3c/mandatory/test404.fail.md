# Testcase: test404

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
KeyError: 's02'

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
statemachine.exceptions.InvalidDefinition: Failed to create state machine class: 's02' from definition: {'states': {'s01p': {'initial': True, 'parallel': True, 'exit': [ExecuteBlock(ExecutableContent(actions=[RaiseAction(event='event3')]))], 'states': [State('S01p1', id='s01p1', value='s01p1', initial=False, final=False), State('S01p2', id='s01p2', value='s01p2', initial=False, final=False), State('S05', id='s05', value='s05', initial=False, final=False)]}, 'pass': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'pass'")]))]}, 'fail': {'final': True, 'enter': [ExecuteBlock(ExecutableContent(actions=[LogAction(label='Outcome', expr="'fail'")]))]}}}

```
