(diagram)=
(diagrams)=
# Diagrams

You can generate visual diagrams from any
{class}`~statemachine.statemachine.StateChart` — useful for documentation,
debugging, or sharing your machine's structure with teammates.

## Installation

Diagram generation requires [pydot](https://github.com/pydot/pydot) and
[Graphviz](https://graphviz.org/):

```bash
pip install python-statemachine[diagrams]  # installs pydot
```

You also need the `dot` command-line tool from Graphviz. On Debian/Ubuntu:

```bash
sudo apt install graphviz
```

For other systems, see the [Graphviz downloads page](https://graphviz.org/download/).


## Generating diagrams

Use `DotGraphMachine` to create a diagram from a class or an instance:

```py
>>> from statemachine.contrib.diagram import DotGraphMachine

>>> from tests.examples.order_control_machine import OrderControl

>>> graph = DotGraphMachine(OrderControl)  # also accepts instances

>>> dot = graph()

>>> dot.to_string()  # doctest: +ELLIPSIS
'digraph OrderControl {...

```

Export to an image file:

```py
>>> dot.write_png("docs/images/order_control_machine_initial.png")

```

![OrderControl](images/order_control_machine_initial.png)

For higher resolution, set the DPI before exporting:

```py
>>> dot.set_dpi(300)

>>> dot.write_png("docs/images/order_control_machine_initial_300dpi.png")

```

![OrderControl (300 DPI)](images/order_control_machine_initial_300dpi.png)

### Highlighting the current state

When you pass a machine **instance** (not a class), the diagram highlights
the current state:

``` py
>>> # This example will only run on automated tests if dot is present
>>> getfixture("requires_dot_installed")

>>> from statemachine.contrib.diagram import DotGraphMachine

>>> from tests.examples.order_control_machine import OrderControl

>>> machine = OrderControl()

>>> graph = DotGraphMachine(machine)  # also accepts instances

>>> machine.receive_payment(10)
[10]

>>> graph().write_png("docs/images/order_control_machine_processing.png")

```

![OrderControl](images/order_control_machine_processing.png)

```{tip}
Every state machine instance exposes a `_graph()` shortcut that returns
the `pydot.Dot` object directly.
```

```py
>>> machine._graph()  # doctest: +ELLIPSIS
<pydot.core.Dot ...

```


## Command line

You can generate diagrams without writing Python code:

```bash
python -m statemachine.contrib.diagram <classpath> <output_file>
```

The output format is inferred from the file extension:

```bash
python -m statemachine.contrib.diagram tests.examples.traffic_light_machine.TrafficLightMachine diagram.png
```

```{note}
Supported formats include `dia`, `dot`, `fig`, `gif`, `jpg`, `pdf`,
`png`, `ps`, `svg`, and many others. See
[Graphviz output formats](https://graphviz.org/docs/outputs/) for the
complete list.
```


## Jupyter integration

State machine instances are automatically rendered as diagrams in
JupyterLab cells — no extra code needed:

![Approval machine on JupyterLab](images/lab_approval_machine_accepted.png)


## Online generation (QuickChart)

If you prefer not to install Graphviz locally, you can generate diagrams
using the [QuickChart](https://quickchart.io/) online service:

```{eval-rst}
.. autofunction:: statemachine.contrib.diagram.quickchart_write_svg
```

![OrderControl](images/oc_machine_processing.svg)
