# coding: utf-8

import pytest

from statemachine.contrib.diagram import DotGraphMachine


@pytest.fixture(params=[
    ("_repr_svg_", '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg'),
    ("_repr_html_", '<div class="statemachine"><?xml version="1.0" encoding="UTF-8" standalone=')
])
def expected_reprs(request):
    return request.param


@pytest.mark.parametrize(
    "machine_name",
    [
        "AllActionsMachine",
        "OrderControl",
    ],
)
def test_machine_repr_custom_(request, machine_name, expected_reprs):
    machine_cls = request.getfixturevalue(machine_name)
    machine = machine_cls()

    magic_method, expected_repr = expected_reprs
    repr = getattr(machine, magic_method)()
    assert repr.startswith(expected_repr)


def test_machine_dot(OrderControl):
    machine = OrderControl()

    graph = DotGraphMachine(machine)
    dot = graph()

    dot_str = dot.to_string()  # or dot.to_string()
    assert dot_str.startswith("digraph list {")
