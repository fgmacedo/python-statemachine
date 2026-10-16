"""Bare-name resolution in native expressions is the same under both evaluators.

A name in a ``cond`` or in a value expression can come from the datamodel, from an attribute
of the bound model or from the keyword arguments passed to ``send``. The restricted
(``trusted=False``) and the trusted evaluators must resolve it to the same value.
"""

import pytest
from statemachine.io import load

DOCUMENT = """
datamodel:
  - {{id: seen, expr: "None"}}
{datamodel}
states:
  wait:
    initial: true
    transitions:
      - event: go
        target: matched
        cond: "{expr} == {expected}"
        on:
          - assign: {{location: seen, expr: "{expr}"}}
      - {{event: go, target: unmatched}}
  matched: {{final: true}}
  unmatched: {{final: true}}
"""

VALUE_FROM_DATAMODEL = '  - {id: value, expr: "1"}'


class InstanceAttribute:
    def __init__(self):
        self.value = 3


class Property:
    @property
    def value(self):
        return 3


class ClassAttribute:
    value = 3


class Slots:
    __slots__ = ("value", "state", "seen")

    def __init__(self):
        self.value = 3


MODEL_KINDS = [
    pytest.param(kind, id=kind.__name__)
    for kind in (InstanceAttribute, Property, ClassAttribute, Slots)
]


@pytest.fixture(params=[False, True], ids=["restricted", "trusted"])
def trusted(request):
    return request.param


def _run(trusted, *, expected, expr="value", datamodel="", model=None, **payload):
    sc = load(
        DOCUMENT.format(datamodel=datamodel, expr=expr, expected=expected),
        format="yaml",
        trusted=trusted,
        validate=True,
    )
    sm = sc() if model is None else sc(model=model())
    sm.send("go", **payload)
    return sm


@pytest.mark.parametrize(
    ("datamodel", "payload", "expected"),
    [
        pytest.param(VALUE_FROM_DATAMODEL, {}, 1, id="datamodel-only"),
        pytest.param("", {"value": 5}, 5, id="kwarg-only"),
    ],
)
def test_name_from_a_single_source(trusted, datamodel, payload, expected):
    sm = _run(trusted, expected=expected, datamodel=datamodel, **payload)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == expected


@pytest.mark.parametrize("model", MODEL_KINDS)
def test_name_from_the_model_only(trusted, model):
    sm = _run(trusted, expected=3, model=model)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 3


def test_event_data_reaches_the_payload(trusted):
    sm = _run(
        trusted, expected=5, expr="_event.data.value", datamodel=VALUE_FROM_DATAMODEL, value=5
    )

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 5


def test_datamodel_shadows_the_payload(trusted):
    sm = _run(trusted, expected=1, datamodel=VALUE_FROM_DATAMODEL, value=5)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 1


@pytest.mark.parametrize("model", MODEL_KINDS)
def test_model_attribute_shadows_the_payload(trusted, model):
    sm = _run(trusted, expected=3, model=model, value=5)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 3


def test_assigned_value_shadows_the_payload(trusted):
    sc = load(
        """
        datamodel:
          - {id: value, expr: "1"}
        states:
          wait:
            initial: true
            transitions:
              - event: update
                on:
                  - assign: {location: value, expr: "7"}
              - {event: go, target: matched, cond: "value == 7"}
              - {event: go, target: unmatched}
          matched: {final: true}
          unmatched: {final: true}
        """,
        format="yaml",
        trusted=trusted,
        validate=True,
    )
    sm = sc()
    sm.send("update")
    sm.send("go", value=5)

    assert sm.configuration_values == {"matched"}


class Method:
    def value(self):
        return 3


def test_trusted_mode_does_not_resolve_a_model_method_by_bare_name():
    sm = _run(True, expected=5, model=Method, value=5)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 5


class BuiltinNamedClassAttribute:
    len = 0
    value = 3


def test_trusted_mode_keeps_builtins_over_model_class_attributes():
    sm = _run(True, expected=1, expr="len([value])", model=BuiltinNamedClassAttribute)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 1
