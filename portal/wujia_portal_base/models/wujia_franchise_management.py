from datetime import datetime

import pytz

from odoo import models

from ..controllers.utils import DEFAULT_PORTAL_TZ


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    def _portal_today(self):
        self.ensure_one()
        tz_name = self.sudo().partner_id.tz
        tz = pytz.timezone(tz_name if tz_name in pytz.all_timezones_set else DEFAULT_PORTAL_TZ)
        return datetime.now(tz).date()

    def _portal_contract_days(self):
        """(số ngày còn lại, đã hết hạn) theo lịch cửa hàng — `remaining_days` stored không tự giảm theo ngày."""
        self.ensure_one()
        end = self.franchise_end_date
        if not end:
            return None, False
        days = (end - self._portal_today()).days
        return days, days < 0
