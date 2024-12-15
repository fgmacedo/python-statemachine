# Testcase: test417

UnboundLocalError: Local name referenced but not bound to a value.

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
  File "/home/macedo/projects/python-statemachine/tests/scxml/test_scxml_cases.py", line 114, in test_scxml_usecase
    processor.parse_scxml_file(testcase_path)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 30, in parse_scxml_file
    return self.parse_scxml(path.stem, scxml_content)
           ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/processor.py", line 33, in parse_scxml
    definition = parse_scxml(scxml_content)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 62, in parse_scxml
    state = parse_state(state_elem, definition.initial_states)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 146, in parse_state
    state.states[child_state.id] = child_state
                                   ^^^^^^^^^^^
UnboundLocalError: cannot access local variable 'child_state' where it is not associated with a value

```
