"""Regression tests for issue #632.

Lazy translation strings (e.g. ``django.utils.translation.gettext_lazy``) are
proxy objects that are *not* real ``str`` instances but are castable via
``str()``.  They must be accepted as a ``State`` / ``Event`` ``name`` and only
resolved (via ``str()``) at the point of display, so the active locale is honored
at render time instead of at class-definition time.
"""

import pytest
from statemachine.contrib.diagram.extract import extract
from statemachine.contrib.diagram.renderers.dot import DotRenderer
from statemachine.contrib.diagram.renderers.mermaid import MermaidRenderer
from statemachine.contrib.diagram.renderers.table import TransitionTableRenderer
from statemachine.exceptions import TransitionNotAllowed

from statemachine import State
from statemachine import StateMachine


class LazyString:
    """Minimal stand-in for a lazy translation proxy.

    It is intentionally **not** a ``str`` subclass: it only resolves to text
    when ``str()`` is called, evaluating ``factory`` each time so a change in the
    active "locale" is reflected at the moment of use.
    """

    def __init__(self, factory):
        self._factory = factory

    def __str__(self):
        return str(self._factory())


# A mutable "locale" the lazy strings below resolve against at call time.
_locale = {"current": "en"}

_TRANSLATIONS = {
    "en": {"start": "Start", "middle": "Middle", "end": "End"},
    "pt": {"start": "Início", "middle": "Meio", "end": "Fim"},
}


def _t(key):
    return LazyString(lambda: _TRANSLATIONS[_locale["current"]][key])


@pytest.fixture(autouse=True)
def reset_locale():
    _locale["current"] = "en"
    yield
    _locale["current"] = "en"


class TranslatedSM(StateMachine):
    start = State(_t("start"), initial=True)
    middle = State(_t("middle"))
    end = State(_t("end"), final=True)

    go = start.to(middle)
    finish = middle.to(end)


def test_transition_not_allowed_message_resolves_lazy_name():
    sm = TranslatedSM()
    with pytest.raises(TransitionNotAllowed) as exc_info:
        sm.finish()  # not allowed from `start`

    assert "Start" in str(exc_info.value)


def test_str_returns_real_str_instance():
    result = str(TranslatedSM.start)
    assert type(result) is str
    assert result == "Start"


def test_state_is_hashable_with_lazy_name():
    state = TranslatedSM.start
    # usable as set member / dict key without raising
    assert state in {state}
    assert {state: 1}[state] == 1


def test_laziness_is_preserved_resolved_at_call_time():
    state = TranslatedSM.start
    assert str(state) == "Start"

    _locale["current"] = "pt"
    # The same state object now resolves to the active locale, proving the
    # lazy object was stored as-is (not coerced at definition time).
    assert str(state) == "Início"


def test_diagram_extract_coerces_lazy_names_to_str():
    graph = extract(TranslatedSM)
    names = {s.id: s.name for s in graph.states}
    assert all(type(n) is str for n in names.values())
    assert names["start"] == "Start"
    assert names["middle"] == "Middle"


def test_mermaid_renderer_with_lazy_names():
    graph = extract(TranslatedSM)
    output = MermaidRenderer().render(graph)
    assert "Start" in output
    assert "Middle" in output


def test_table_renderer_with_lazy_names():
    graph = extract(TranslatedSM)
    output = TransitionTableRenderer().render(graph)
    assert "Start" in output
    assert "Middle" in output


def test_dot_renderer_with_lazy_names():
    graph = extract(TranslatedSM)
    dot = DotRenderer().render(graph)
    assert "Start" in str(dot)
