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

For those looking to generate diagrams from your state machines, [pydot](https://github.com/pydot/pydot) and [Graphviz](https://graphviz.org/) are required.
Conveniently, you can install python-statemachine along with the `pydot` dependency using the extras option.
For more information, please refer to our documentation.

```shell
python3 -m pip install "python-statemachine[diagrams]"
```



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
