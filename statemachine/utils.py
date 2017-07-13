# coding: utf-8
from __future__ import absolute_import, unicode_literals


try:
    from django.utils.translation import ugettext
except Exception:
    def ugettext(text):
        return text
