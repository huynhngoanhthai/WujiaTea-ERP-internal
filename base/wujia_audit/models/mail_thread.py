# -*- coding: utf-8 -*-
from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _track_get_fields(self):
        """Override to combine native code-level tracking with dynamic configured fields."""
        tracked_fields = super()._track_get_fields() or set()

        # Read from ormcache (0ms)
        custom_fields = self.env['wujia.field.tracking.config']._get_tracked_fields_cache(self._name)
        if custom_fields:
            valid_custom_fields = {f for f in custom_fields if f in self._fields}
            tracked_fields = set(tracked_fields) | valid_custom_fields

        return tracked_fields
