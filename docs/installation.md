# Installation


## Stable release

To install Python State Machine, if you're using [poetry](https://python-poetry.org/):

    poetry add python-statemachine


Or to install using [pip](https://pip.pypa.io):

    pip install python-statemachine


To generate diagrams from your machines, you'll also need `pydot` and `Graphviz`. You can
install this library already with `pydot` dependency using the `extras` install option. See
our docs for more details.

    pip install python-statemachine[diagrams]


If you don't have [pip](https://pip.pypa.io) installed, this [Python installation guide](http://docs.python-guide.org/en/latest/starting/installation/) can guide
you through the process.


## From sources

The sources for Python State Machine can be downloaded from the [Github repo](https://github.com/fgmacedo/python-statemachine).

You can either clone the public repository:

    git clone git://github.com/fgmacedo/python-statemachine

Or download the `tarball`:

    curl  -OL https://github.com/fgmacedo/python-statemachine/tarball/master

Once you have a copy of the source, you can install it with:

    python setup.py install
