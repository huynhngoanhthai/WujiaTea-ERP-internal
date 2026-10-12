# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""Shared validation helpers for dashboard constraints."""
import re

from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo import _

HEX_COLOR_RE = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$')
CACHE_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def assert_hex_color(value, field_label=None):
    """Raise if value is set and not a valid CSS hex color."""
    if not value:
        return
    label = field_label or _('Color')
    if not HEX_COLOR_RE.match(str(value).strip()):
        raise ValidationError(
            _('%(field)s must be a valid hex color (e.g. #FFF or #4A90E2). Got: %(value)s',
              field=label, value=value)
        )


def assert_domain(value, field_label=None):
    """Raise if domain string is not a Python list/tuple literal."""
    if value in (False, None, ''):
        return
    label = field_label or _('Domain')
    try:
        domain = safe_eval(value)
    except Exception as e:
        raise ValidationError(
            _('%(field)s is not a valid domain expression: %(error)s',
              field=label, error=e)
        ) from e
    if not isinstance(domain, (list, tuple)):
        raise ValidationError(
            _('%(field)s must evaluate to a list (got %(type)s).',
              field=label, type=type(domain).__name__)
        )


def assert_json_object(value, field_label=None):
    """Raise if value is set and is not a JSON object/array."""
    if not value:
        return
    import json
    label = field_label or _('JSON')
    try:
        parsed = json.loads(value)
    except Exception as e:
        raise ValidationError(
            _('%(field)s must be valid JSON: %(error)s',
              field=label, error=e)
        ) from e
    if not isinstance(parsed, (dict, list)):
        raise ValidationError(
            _('%(field)s must be a JSON object or array.', field=label)
        )
