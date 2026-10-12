# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Invalidate financial-report payloads when exchange rates change."""

from odoo import api, models


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    def _eh_invalidate_report_cache(self):
        self.env['res.company'].sudo()._eh_bump_global_report_version()

    @api.model_create_multi
    def create(self, vals_list):
        rates = super().create(vals_list)
        rates._eh_invalidate_report_cache()
        return rates

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'rate', 'company_rate', 'inverse_company_rate',
                'currency_id', 'company_id'}.intersection(vals):
            self._eh_invalidate_report_cache()
        return result

    def unlink(self):
        invalidate = bool(self)
        result = super().unlink()
        if invalidate:
            self._eh_invalidate_report_cache()
        return result


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'symbol', 'position', 'rounding',
                'active'}.intersection(vals):
            self.env['res.company'].sudo()._eh_bump_global_report_version()
        return result
