# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _


class DynamicDashboardCategory(models.Model):
    _name = 'dynamic.dashboard.category'
    _description = 'Dashboard Category'
    _order = 'sequence, name, id'

    name = fields.Char(string='Category', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')
    dashboard_count = fields.Integer(compute='_compute_dashboard_count')

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        'Category name must be unique.',
    )

    @api.depends()
    def _compute_dashboard_count(self):
        Dash = self.env['dynamic.dashboard']
        for cat in self:
            cat.dashboard_count = Dash.search_count([('category_id', '=', cat.id)])

    @api.model
    def get_or_create(self, name):
        """Return a category for a label, creating it when missing."""
        label = (name or '').strip()
        if not label:
            return self.browse()
        existing = self.search([('name', '=', label)], limit=1)
        if existing:
            return existing
        return self.create({'name': label})
