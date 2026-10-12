# -*- coding: utf-8 -*-
from odoo import api, fields, models


class IrModel(models.Model):
    _inherit = 'ir.model'

    is_mail_thread = fields.Boolean(
        string='Has Chatter (mail.thread)',
        compute='_compute_is_mail_thread',
        store=True,
        index=True,
        help='Indicates if this model inherits from mail.thread and supports chatter message tracking.',
    )

    @api.depends('model')
    def _compute_is_mail_thread(self):
        mail_thread_pool = self.pool.get('mail.thread')
        for rec in self:
            try:
                if rec.model and rec.model in self.env and mail_thread_pool:
                    model_class = self.env[rec.model]
                    rec.is_mail_thread = bool(issubclass(type(model_class), mail_thread_pool))
                else:
                    rec.is_mail_thread = False
            except Exception:
                rec.is_mail_thread = False

