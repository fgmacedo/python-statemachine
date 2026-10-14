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


class Holder:
    def __init__(self, value):
        self.value = value


@pytest.fixture(params=[False, True], ids=["restricted", "trusted"])
def trusted(request):
    return request.param


def _run(trusted, *, expected, expr="value", datamodel="", model_value=None, **payload):
    sc = load(
        DOCUMENT.format(datamodel=datamodel, expr=expr, expected=expected),
        format="yaml",
        trusted=trusted,
        validate=True,
    )
    sm = sc() if model_value is None else sc(model=Holder(model_value))
    sm.send("go", **payload)
    return sm


@pytest.mark.parametrize(
    ("datamodel", "model_value", "payload", "expected"),
    [
        pytest.param(VALUE_FROM_DATAMODEL, None, {}, 1, id="datamodel-only"),
        pytest.param("", 3, {}, 3, id="model-only"),
        pytest.param("", None, {"value": 5}, 5, id="kwarg-only"),
    ],
)
def test_name_from_a_single_source(trusted, datamodel, model_value, payload, expected):
    sm = _run(trusted, expected=expected, datamodel=datamodel, model_value=model_value, **payload)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == expected


def test_event_data_reaches_the_payload(trusted):
    sm = _run(
        trusted, expected=5, expr="_event.data.value", datamodel=VALUE_FROM_DATAMODEL, value=5
    )

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 5


@pytest.mark.parametrize(
    ("datamodel", "model_value", "expected"),
    [
        pytest.param(VALUE_FROM_DATAMODEL, None, 1, id="datamodel-and-kwarg"),
        pytest.param("", 3, 3, id="model-and-kwarg"),
    ],
)
def test_datamodel_shadows_the_payload(trusted, datamodel, model_value, expected):
    sm = _run(trusted, expected=expected, datamodel=datamodel, model_value=model_value, value=5)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == expected


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
