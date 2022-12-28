# coding: utf-8
from __future__ import absolute_import, unicode_literals
import inspect


try:
    from django.utils.translation import ugettext
except Exception:
    def ugettext(text):
        return text


def _is_callable_with_kwargs(f):
    # python 3 variant -> return inspect.getfullargspec(f).varkw is not None
    return inspect.getargspec(f).keywords is not None


def call_with_args(f, *args, **kwargs):
    if _is_callable_with_kwargs(f):
        f(*args, **kwargs)
    else:
        f()


def _is_string(obj):
    return isinstance(obj, (str, type(u"")))  # type(u""") is a small hack for Python2


def ensure_iterable(obj):
    if _is_string(obj):
        return [obj]
    try:
        return iter(obj)
    except TypeError:
        return [obj]
