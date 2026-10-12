# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import secrets
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError


class DynamicDashboardShare(models.Model):
    _name = 'dynamic.dashboard.share'
    _description = 'Dashboard Share Token'
    _order = 'create_date desc'
    _check_company_auto = True

    _token_uniq = models.Constraint(
        'UNIQUE(token)',
        'Share tokens must be unique.',
    )
    _expiry_hours_positive = models.Constraint(
        'CHECK(expiry_hours >= 1)',
        'Expiry hours must be at least 1.',
    )
    _access_count_positive = models.Constraint(
        'CHECK(access_count IS NULL OR access_count >= 0)',
        'Access count cannot be negative.',
    )

    name = fields.Char(required=True, default='Share Link')
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', required=True, ondelete='cascade', check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='dashboard_id.company_id', store=True, index=True,
    )
    token = fields.Char(required=True, copy=False, default=lambda self: secrets.token_urlsafe(24), index=True)
    expiry_hours = fields.Integer(string='Expiry Hours', default=72)
    expires_at = fields.Datetime(compute='_compute_expires_at', store=True)
    active = fields.Boolean(default=True)
    access_count = fields.Integer(readonly=True, default=0)

    @api.constrains('token')
    def _check_token(self):
        for share in self:
            if not share.token or len(share.token) < 8:
                raise ValidationError(_('Share token is too short or missing.'))

    @api.depends('create_date', 'expiry_hours')
    def _compute_expires_at(self):
        for rec in self:
            base = rec.create_date or fields.Datetime.now()
            hours = max(1, rec.expiry_hours or 72)
            rec.expires_at = base + timedelta(hours=hours)

    def action_open_link(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return {
            'type': 'ir.actions.act_url',
            'url': f'{base}/dynamic_dashboard_ai_nexgen/share/{self.token}',
            'target': 'new',
        }

    @api.model
    def get_dashboard_by_token(self, token):
        share = self.sudo().search([('token', '=', token), ('active', '=', True)], limit=1)
        if not share:
            raise AccessError(_('Invalid share link.'))
        if share.expires_at and share.expires_at < fields.Datetime.now():
            raise AccessError(_('This share link has expired.'))
        share.sudo().write({'access_count': share.access_count + 1})
        return share.dashboard_id
