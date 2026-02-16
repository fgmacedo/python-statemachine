# Testcase: test532

ValueError: Inappropriate argument value (of correct type).

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
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/tests/scxml/test_scxml_cases.py", line 162, in _run_scxml_testcase
    processor.parse_scxml_file(testcase_path)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/processor.py", line 78, in parse_scxml_file
    return self.parse_scxml(path.stem, scxml_content)
           ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/processor.py", line 81, in parse_scxml
    definition = parse_scxml(scxml_content)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/parser.py", line 70, in parse_scxml
    state = parse_state(state_elem, all_initial_states)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/parser.py", line 150, in parse_state
    content = parse_executable_content(onentry_elem)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/parser.py", line 297, in parse_executable_content
    action = parse_element(child)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/parser.py", line 314, in parse_element
    return parse_send(element)
  File "/Users/fernando.macedo/projects/python-statemachine-invoke/statemachine/io/scxml/parser.py", line 385, in parse_send
    raise ValueError("<send> must have an 'event' or `eventexpr` attribute")
ValueError: <send> must have an 'event' or `eventexpr` attribute

```
