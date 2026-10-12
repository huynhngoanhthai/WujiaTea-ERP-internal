# -*- coding: utf-8 -*-
from odoo import models


class Base(models.AbstractModel):
    _inherit = 'base'

    def _eh_check_access(self, operation):
        """Check model ACLs and record rules on every supported Odoo series."""
        # Odoo 16-18 keeps ir.attachment linked-resource/owner security in
        # its legacy ``check`` method rather than BaseModel.check_access().
        legacy_attachment_check = (
            getattr(self, 'check', None)
            if self._name == 'ir.attachment'
            else None
        )
        if callable(legacy_attachment_check):
            legacy_attachment_check(operation)
            return
        check_access = getattr(self, 'check_access', None)
        if check_access:
            check_access(operation)
            return
        self.check_access_rights(operation)
        self.check_access_rule(operation)
