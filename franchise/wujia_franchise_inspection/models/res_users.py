# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    inspection_signature = fields.Binary(
        string='Inspection Signature / Digital Signature',
        attachment=True,
        copy=False,
        help='Default signature used for store inspection & supervision sheets.'
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['inspection_signature']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['inspection_signature']
