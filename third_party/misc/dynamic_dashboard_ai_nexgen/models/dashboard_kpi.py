# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import base64
import csv
import io
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class DynamicDashboardKpi(models.Model):
    _name = 'dynamic.dashboard.kpi'
    _description = 'Hierarchical Dashboard KPI'
    _order = 'sequence, name, id'
    _parent_store = True
    _check_company_auto = True

    _alert_threshold_range = models.Constraint(
        'CHECK(alert_threshold_pct IS NULL OR (alert_threshold_pct >= 0 AND alert_threshold_pct <= 1000))',
        'Alert threshold must be between 0 and 1000.',
    )
    _alert_cooldown_positive = models.Constraint(
        'CHECK(alert_cooldown_hours IS NULL OR alert_cooldown_hours >= 1)',
        'Alert cooldown must be at least 1 hour.',
    )

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True,
    )
    parent_id = fields.Many2one(
        'dynamic.dashboard.kpi', string='Parent KPI', ondelete='cascade',
        index=True, check_company=True,
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('dynamic.dashboard.kpi', 'parent_id', string='Child KPIs')

    computation_mode = fields.Selection([
        ('model', 'Odoo Model'),
        ('formula', 'Formula'),
        ('children', 'Sum of Children'),
    ], default='model', required=True)

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        ondelete='cascade',
        domain="[('transient', '=', False)]",
    )
    model_name = fields.Char(string='Model Technical Name', related='model_id.model', readonly=True)
    measure_field_id = fields.Many2one(
        'ir.model.fields',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['integer', 'float', 'monetary']), ('name', '!=', 'id')]",
        ondelete='cascade',
    )
    aggregation = fields.Selection([
        ('sum', 'Sum'), ('count', 'Count'), ('average', 'Average'),
    ], default='sum')
    domain = fields.Char(default='[]')
    date_filter_field_id = fields.Many2one(
        'ir.model.fields',
        domain="[('model_id', '=', model_id), ('store', '=', True), ('ttype', 'in', ['date', 'datetime'])]",
        ondelete='cascade',
    )
    formula = fields.Char(help='Use {child_name} or numeric literals, e.g. {Revenue}/{Cost}')
    unit = fields.Selection(
        selection='_selection_units',
        string='Unit',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency used when this KPI is displayed on a dashboard.',
    )
    current_value = fields.Float(readonly=True)
    target_value = fields.Float(compute='_compute_target_value', store=False)
    achievement = fields.Float(string='Achievement %', compute='_compute_achievement')
    last_computed = fields.Datetime(readonly=True)
    target_ids = fields.One2many('dynamic.dashboard.kpi.target', 'kpi_id', string='Targets')

    # Alert notifications (cron)
    alert_enabled = fields.Boolean(
        string='Alert When Below Target',
        default=False,
        help='Send inbox/email notifications when achievement falls below the threshold.',
    )
    alert_threshold_pct = fields.Float(
        string='Alert Below (%)',
        default=80.0,
        help='Notify when Achievement % is strictly below this value.',
    )
    alert_user_ids = fields.Many2many(
        'res.users',
        'dynamic_dashboard_ai_nexgen_kpi_alert_user_rel',
        'kpi_id',
        'user_id',
        string='Alert Recipients',
    )
    alert_cooldown_hours = fields.Integer(
        string='Alert Cooldown (hours)',
        default=24,
        help='Minimum hours between repeated alerts for the same KPI.',
    )
    alert_last_notified = fields.Datetime(string='Last Alert Sent', readonly=True)

    @api.model
    def _selection_units(self):
        return self.env['dynamic.dashboard.item']._selection_units()

    @api.constrains('parent_id')
    def _check_parent_id(self):
        for kpi in self:
            if kpi.parent_id and kpi.parent_id == kpi:
                raise ValidationError(_('A KPI cannot be its own parent.'))
            if kpi.parent_id and kpi in kpi.parent_id._get_ancestors():
                raise ValidationError(
                    _('You cannot create a recursive KPI hierarchy for "%s".') % kpi.display_name
                )

    def _get_ancestors(self):
        self.ensure_one()
        ancestors = self.env['dynamic.dashboard.kpi']
        parent = self.parent_id
        while parent:
            if parent in ancestors:
                break
            ancestors |= parent
            parent = parent.parent_id
        return ancestors

    @api.constrains('computation_mode', 'model_id', 'formula', 'aggregation', 'measure_field_id', 'domain')
    def _check_computation_config(self):
        from .constraints_utils import assert_domain
        for kpi in self:
            assert_domain(kpi.domain, _('KPI Domain'))
            if kpi.computation_mode == 'model' and not kpi.model_id:
                raise ValidationError(
                    _('Model is required when computation mode is "Odoo Model" (%s).')
                    % kpi.display_name
                )
            if kpi.computation_mode == 'model' and kpi.aggregation in ('sum', 'average') and not kpi.measure_field_id:
                raise ValidationError(
                    _('Measure field is required for Sum/Average KPIs (%s).') % kpi.display_name
                )
            if kpi.computation_mode == 'formula' and not (kpi.formula or '').strip():
                raise ValidationError(
                    _('Formula is required when computation mode is "Formula" (%s).')
                    % kpi.display_name
                )

    @api.constrains('alert_enabled', 'alert_user_ids')
    def _check_alert_recipients(self):
        for kpi in self:
            if kpi.alert_enabled and not kpi.alert_user_ids:
                raise ValidationError(
                    _('Alert recipients are required when KPI alerts are enabled (%s).')
                    % kpi.display_name
                )

    @api.depends('target_ids', 'target_ids.period_start', 'target_ids.period_end', 'target_ids.target_value')
    def _compute_target_value(self):
        today = fields.Date.context_today(self)
        for kpi in self:
            target = kpi.target_ids.filtered(
                lambda t: (not t.period_start or t.period_start <= today)
                and (not t.period_end or t.period_end >= today)
            )[:1]
            kpi.target_value = target.target_value if target else 0.0

    @api.depends('current_value', 'target_value')
    def _compute_achievement(self):
        for kpi in self:
            if kpi.target_value:
                kpi.achievement = (kpi.current_value / kpi.target_value) * 100.0
            else:
                kpi.achievement = 0.0

    def action_compute_now(self):
        self._compute_values()
        return True

    def _compute_values(self, date_filter='none'):
        # Children first (bottom-up)
        for kpi in self.sorted(lambda k: (k.parent_path or '').count('/'), reverse=True):
            kpi._compute_one(date_filter=date_filter)

    def _compute_one(self, date_filter='none'):
        self.ensure_one()
        val = 0.0
        if self.computation_mode == 'children':
            val = sum(self.child_ids.mapped('current_value'))
        elif self.computation_mode == 'formula':
            ctx = {c.name: c.current_value for c in self.child_ids}
            expr = self.formula or '0'
            for name, v in ctx.items():
                expr = expr.replace('{%s}' % name, str(v))
            try:
                val = float(safe_eval(expr, {'__builtins__': {}}, mode='eval'))
            except Exception:
                val = 0.0
        elif self.computation_mode == 'model' and self.model_id:
            Item = self.env['dynamic.dashboard.item']
            Model = Item._dd_scoped_model(self.sudo().model_id.model)
            domain = list(safe_eval(self.domain or '[]'))
            if self.date_filter_field_id and date_filter and date_filter != 'none':
                today = fields.Date.context_today(self)
                start, end, _, _ = Item._resolve_date_range(date_filter, today=today)
                if start and end:
                    domain += [
                        (self.date_filter_field_id.name, '>=', start),
                        (self.date_filter_field_id.name, '<=', end),
                    ]
            agg = self.aggregation or 'sum'
            if agg == 'count' or not self.measure_field_id:
                val = Model.search_count(domain)
            else:
                fname = self.measure_field_id.name
                orm_agg = 'avg' if agg == 'average' else agg
                grouped = Model.read_group(domain, [f'{fname}:{orm_agg}'], [])
                val = grouped[0].get(fname) or 0 if grouped else 0
        self.write({
            'current_value': val or 0.0,
            'last_computed': fields.Datetime.now(),
        })

    def get_dashboard_payload(self, date_filter='none'):
        self.ensure_one()
        self._compute_one(date_filter=date_filter)
        from .l10n_utils import serialize_currency, resolve_display_currency
        currency = resolve_display_currency(self.env, company=self.company_id, explicit=self.currency_id)
        return {
            'value': self.current_value,
            'target_value': self.target_value,
            'achievement': self.achievement,
            'unit': self.unit or '',
            'name': self.name,
            'currency': serialize_currency(currency),
            'scorecard_values': [{
                'label': self.name,
                'value': self.current_value,
                'target': self.target_value,
                'achievement': self.achievement,
            }] + [{
                'label': c.name,
                'value': c.current_value,
                'target': c.target_value,
                'achievement': c.achievement,
            } for c in self.child_ids],
        }

    def _should_send_alert(self):
        self.ensure_one()
        if not self.alert_enabled or not self.alert_user_ids:
            return False
        if not self.target_value:
            return False
        if self.achievement >= (self.alert_threshold_pct or 0.0):
            return False
        if self.alert_last_notified:
            cooldown = max(1, self.alert_cooldown_hours or 24)
            if fields.Datetime.now() - self.alert_last_notified < timedelta(hours=cooldown):
                return False
        return True

    def _notify_underperforming(self):
        """Push inbox notifications (and email per user prefs) for under-target KPIs."""
        for kpi in self:
            if not kpi._should_send_alert():
                continue
            partners = kpi.alert_user_ids.mapped('partner_id').filtered('email')
            if not partners:
                partners = kpi.alert_user_ids.mapped('partner_id')
            if not partners:
                continue
            subject = _('KPI Alert: %s below target') % kpi.name
            body = Markup(
                '<p><b>%(name)s</b> is at <b>%(ach).1f%%</b> of target '
                '(threshold %(thr).1f%%).</p>'
                '<ul>'
                '<li>Current: %(cur)s%(unit)s</li>'
                '<li>Target: %(tgt)s%(unit)s</li>'
                '</ul>'
            ) % {
                'name': escape(kpi.name),
                'ach': kpi.achievement or 0.0,
                'thr': kpi.alert_threshold_pct or 0.0,
                'cur': kpi.current_value,
                'tgt': kpi.target_value,
                'unit': escape(f' {kpi.unit}' if kpi.unit else ''),
            }
            try:
                self.env['mail.thread'].message_notify(
                    partner_ids=partners.ids,
                    subject=subject,
                    body=body,
                    model=kpi._name,
                    res_id=kpi.id,
                    subtype_xmlid='mail.mt_note',
                )
                kpi.alert_last_notified = fields.Datetime.now()
            except Exception:
                _logger.exception('KPI alert notification failed for %s', kpi.name)

    @api.model
    def _cron_compute_kpis(self):
        kpis = self.search([('active', '=', True)])
        kpis._compute_values()
        kpis._notify_underperforming()
        return True

    def action_export_targets(self):
        self.ensure_one()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['period_start', 'period_end', 'target_value', 'name'])
        for t in self.target_ids:
            writer.writerow([t.period_start or '', t.period_end or '', t.target_value, t.name or ''])
        data = base64.b64encode(buf.getvalue().encode('utf-8'))
        att = self.env['ir.attachment'].create({
            'name': f'{self.name}_targets.csv',
            'type': 'binary',
            'datas': data,
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{att.id}?download=true',
            'target': 'self',
        }

    def action_import_targets_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import KPI Targets'),
            'res_model': 'dynamic.dashboard.kpi.target.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_kpi_id': self.id},
        }


class DynamicDashboardKpiTarget(models.Model):
    _name = 'dynamic.dashboard.kpi.target'
    _description = 'KPI Target'
    _order = 'period_start desc, id'
    _check_company_auto = True

    name = fields.Char()
    kpi_id = fields.Many2one(
        'dynamic.dashboard.kpi', required=True, ondelete='cascade', check_company=True,
    )
    company_id = fields.Many2one(
        'res.company', related='kpi_id.company_id', store=True, index=True,
    )
    period_start = fields.Date()
    period_end = fields.Date()
    target_value = fields.Float(required=True)

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        for line in self:
            if line.period_start and line.period_end and line.period_start > line.period_end:
                raise ValidationError(
                    _('KPI target period start must be on or before period end.')
                )


class DynamicDashboardKpiTargetImport(models.TransientModel):
    _name = 'dynamic.dashboard.kpi.target.import'
    _description = 'Import KPI Targets CSV'

    kpi_id = fields.Many2one('dynamic.dashboard.kpi', required=True)
    data_file = fields.Binary(required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        raw = base64.b64decode(self.data_file)
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8')))
        Target = self.env['dynamic.dashboard.kpi.target']
        for row in reader:
            Target.create({
                'kpi_id': self.kpi_id.id,
                'name': row.get('name') or False,
                'period_start': row.get('period_start') or False,
                'period_end': row.get('period_end') or False,
                'target_value': float(row.get('target_value') or 0),
            })
        return {'type': 'ir.actions.act_window_close'}
