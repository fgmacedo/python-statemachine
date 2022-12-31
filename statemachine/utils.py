# coding: utf-8
from __future__ import absolute_import, unicode_literals


try:
    from django.utils.translation import ugettext
except Exception:

    def ugettext(text):
        return text


def _is_string(obj):
    return isinstance(obj, (str, type("")))  # type(u""") is a small hack for Python2


def ensure_iterable(obj):
    if _is_string(obj):
        return [obj]
    try:
        return iter(obj)
    except TypeError:
        return [obj]


def check_state_factory(state):
    "Return a property that checks if the current state is the desired state"

    @property
    def is_in_state(self):
        return bool(self.current_state == state)

    return is_in_state
