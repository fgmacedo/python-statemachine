# Testcase: test504

KeyError: Mapping key not found.

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
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 68, in parse_scxml
    state = parse_state(state_elem, definition.initial_states, is_parallel=True)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 124, in parse_state
    content = parse_executable_content(onexit_elem)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 176, in parse_executable_content
    action = parse_element(child)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 189, in parse_element
    return parse_log(element)
  File "/home/macedo/projects/python-statemachine/statemachine/io/scxml/parser.py", line 217, in parse_log
    expr = element.attrib["expr"]
           ~~~~~~~~~~~~~~^^^^^^^^
KeyError: 'expr'

```