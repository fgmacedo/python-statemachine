# JSON Schema

The native JSON/YAML format is described by a published
[JSON Schema](https://json-schema.org/) (Draft 2020-12), shipped with the package at
`statemachine/io/schemas/statechart.schema.json` and identified by:

```
https://fgmacedo.github.io/python-statemachine/schemas/statechart/v1.json
```

This lets editors and external tools validate and autocomplete statechart documents.
Reference it from a YAML file so your editor validates as you type:

```yaml
# yaml-language-server: $schema=https://fgmacedo.github.io/python-statemachine/schemas/statechart/v1.json
name: Traffic light
states:
  green:
    initial: true
```

## Validating at load time

Pass `validate=True` to {func}`~statemachine.io.load` to validate a document against the
schema before building it. This requires the optional `[validation]` extra
(`pip install "python-statemachine[validation]"`, which installs `jsonschema`):

```py
>>> from statemachine.io import load

>>> sc = load(
...     '{"name": "M", "states": {"a": {"initial": true}}}',
...     format="json",
...     validate=True,
... )
>>> sc.__name__
'M'

```

An invalid document raises `InvalidDefinition` with the
schema violation:

```py
>>> from statemachine.exceptions import InvalidDefinition

>>> try:
...     load('{"states": {"a": {"surprise": 1}}}', format="json", validate=True)
... except InvalidDefinition as exc:
...     print("rejected")
rejected

```

Validation applies to the native JSON/YAML format only; SCXML is validated as XML by its
own parser.
