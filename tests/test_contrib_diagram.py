# coding: utf-8

import pytest

from statemachine.contrib.diagram import DotGraphMachine


@pytest.mark.parametrize("machine_name", [
    "AllActionsMachine",
    "OrderControl",
])
def test_machine_repr_svg_(request, machine_name):
    machine_cls = request.getfixturevalue(machine_name)
    machine = machine_cls()
    svg = machine._repr_svg_()
    assert svg.startswith('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg')


def test_machine_dot(OrderControl):
    machine = OrderControl()

    graph = DotGraphMachine(machine)
    dot = graph()

    dot_str = dot.to_string()  # or dot.to_string()
    assert dot_str.startswith("digraph list {")
