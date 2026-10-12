# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MetabaseInstance(models.Model):
    _name = 'metabase.instance'
    _description = 'Metabase BI Instance Server'
    _order = 'name, id'

    name = fields.Char(string='Connection Name', required=True)
    base_url = fields.Char(
        string='Metabase Server Base URL',
        required=True,
        help='Base URL of the Metabase server, e.g., https://bi-wujia.tipscode.io'
    )
    embedding_secret = fields.Char(
        string='JWT Embedding Secret Key',
        required=True,
        help='Hex secret key from Metabase Admin > Embedding > Embedding in other applications'
    )
    token_expiry_minutes = fields.Integer(
        string='Token Expiry (Minutes)',
        default=10,
        required=True,
        help='Expiration time for generated JWT tokens in minutes.'
    )
    active = fields.Boolean(string='Active', default=True)
    company_ids = fields.Many2many(
        'res.company',
        string='Allowed Companies',
        default=lambda self: [(6, 0, [self.env.company.id])],
        help='Companies permitted to access this Metabase instance.'
    )
    dashboard_ids = fields.One2many(
        'metabase.dashboard',
        'instance_id',
        string='Dashboards'
    )

    @api.constrains('token_expiry_minutes')
    def _check_token_expiry(self):
        for rec in self:
            if rec.token_expiry_minutes <= 0:
                raise ValidationError(_("Token expiry minutes must be greater than 0."))

    @api.constrains('base_url')
    def _check_base_url(self):
        for rec in self:
            if rec.base_url:
                url = rec.base_url.strip().rstrip('/')
                if url != rec.base_url:
                    rec.base_url = url
