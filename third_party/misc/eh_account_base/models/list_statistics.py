# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Small, read-only list statistics shared by accounting-suite models.

Statistics remain non-stored and are computed for the prefetched list-page
recordset.  Contributors must batch their reads; this mixin deliberately does
not perform a query or persist a counter itself.
"""

import math
import re
from collections import defaultdict

from odoo import _, api, fields, models


_ICON_CLASS_RE = re.compile(r'^fa-[a-z0-9-]+$')
_TAG_CLASS_RE = re.compile(r'^o_tag_color_(?:[0-9]|1[01])$')
# Statistics are a non-stored, read-only payload produced by trusted Python
# hooks.  Keep client-callable methods inside the suite's view-only naming
# convention; workflow/mutation methods never cross this boundary.
_ACTION_METHOD_RE = re.compile(r'^action_view_[a-z0-9_]+$')
_MAX_STATISTICS = 8
_MAX_LABEL_LENGTH = 80
_MAX_VALUE_LENGTH = 40


class EhListStatisticsMixin(models.AbstractModel):
    _name = 'eh.list.statistics.mixin'
    _description = 'ERP Heritage List Statistics Mixin'

    eh_list_statistics = fields.Json(
        string='Statistics',
        compute='_compute_eh_list_statistics',
        readonly=True,
    )

    @api.depends_context('uid', 'allowed_company_ids', 'company')
    def _compute_eh_list_statistics(self):
        statistics_by_record = self._eh_list_statistics_hook() or {}
        for record in self:
            entries = statistics_by_record.get(record.id, [])
            record.eh_list_statistics = self._eh_sanitize_list_statistics(
                entries,
            )

    def _eh_list_statistics_hook(self):
        """Return ``record id -> badge payloads`` for this recordset.

        Overrides append to the returned lists and must batch any database
        work across ``self``.  Returning an empty mapping is query-free and
        gives every row an empty payload (``fields.Json`` may expose it as
        ``False`` on older series).
        """
        return defaultdict(list)

    @api.model
    def _eh_sanitize_list_statistics(self, entries):
        """Normalize an extension payload without failing list rendering."""
        if not isinstance(entries, (list, tuple)):
            return []

        sanitized = []
        for entry in entries:
            if len(sanitized) >= _MAX_STATISTICS:
                break
            if not isinstance(entry, dict):
                continue

            value = entry.get('value')
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, float) and not math.isfinite(value):
                continue
            if not isinstance(value, (int, float, str)):
                continue
            if isinstance(value, str):
                value = value[:_MAX_VALUE_LENGTH]

            icon_class = entry.get('iconClass')
            if not isinstance(icon_class, str) or not _ICON_CLASS_RE.fullmatch(
                    icon_class):
                icon_class = 'fa-circle'

            label = entry.get('label')
            try:
                label = str(label) if label else _('Statistic')
            except (TypeError, ValueError):
                label = _('Statistic')

            result = {
                'iconClass': icon_class,
                'value': value,
                'label': label[:_MAX_LABEL_LENGTH],
            }
            tag_class = entry.get('tagClass')
            if isinstance(tag_class, str) and _TAG_CLASS_RE.fullmatch(
                    tag_class):
                result['tagClass'] = tag_class
            action_method = entry.get('actionMethod')
            if (
                isinstance(action_method, str)
                and _ACTION_METHOD_RE.fullmatch(action_method)
            ):
                result['actionMethod'] = action_method
            sanitized.append(result)
        return sanitized
