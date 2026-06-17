# Installation


## Latest release

To install using [uv](https://docs.astral.sh/uv):

```shell
uv add python-statemachine
```

To install using [poetry](https://python-poetry.org/):

```shell
poetry add python-statemachine
```

Alternatively, if you prefer using [pip](https://pip.pypa.io):

```shell
python3 -m pip install python-statemachine
```

## Optional extras

Some features require extra dependencies, available as pip extras:

```shell
python3 -m pip install "python-statemachine[diagrams]"    # pydot, to generate diagrams from your machines
python3 -m pip install "python-statemachine[yaml]"        # PyYAML, to load YAML statechart documents
python3 -m pip install "python-statemachine[validation]"  # jsonschema, to validate documents (validate=True)
python3 -m pip install "python-statemachine[io]"          # PyYAML + jsonschema, the full JSON/YAML IO stack
```

Diagram generation also requires the [Graphviz](https://graphviz.org/) system package (see
[](diagram.md)). The `[yaml]`, `[validation]` and `[io]` extras back the declarative loaders
documented in [](io/index.md); loading JSON needs no extra, as it uses only the standard library.



## From sources

The sources for Python State Machine can be downloaded from the [Github repo](https://github.com/fgmacedo/python-statemachine).

You can either clone the public repository:

```shell
git clone git://github.com/fgmacedo/python-statemachine
```

Or download the `tarball`:

```shell
curl  -OL https://github.com/fgmacedo/python-statemachine/tarball/main
```

Once you have a copy of the source, you can install it with:

```shell
python3 -m pip install -e .
```
