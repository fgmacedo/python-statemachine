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


def _run(trusted, *, expected, expr="value", datamodel="", model=None, **payload):
    sc = load(
        DOCUMENT.format(datamodel=datamodel, expr=expr, expected=expected),
        format="yaml",
        trusted=trusted,
        validate=True,
    )
    sm = sc(model=model) if model is not None else sc()
    sm.send("go", **payload)
    return sm


@pytest.mark.parametrize(
    ("datamodel", "model", "payload", "expected"),
    [
        pytest.param(VALUE_FROM_DATAMODEL, None, {}, 1, id="datamodel-only"),
        pytest.param("", Holder(3), {}, 3, id="model-only"),
        pytest.param("", None, {"value": 5}, 5, id="kwarg-only"),
    ],
)
def test_name_from_a_single_source(trusted, datamodel, model, payload, expected):
    sm = _run(trusted, expected=expected, datamodel=datamodel, model=model, **payload)

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == expected


def test_event_data_reaches_the_payload(trusted):
    sm = _run(
        trusted, expected=5, expr="_event.data.value", datamodel=VALUE_FROM_DATAMODEL, value=5
    )

    assert sm.configuration_values == {"matched"}
    assert sm.model.seen == 5
