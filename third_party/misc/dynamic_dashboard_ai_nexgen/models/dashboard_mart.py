# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from markupsafe import Markup, escape
from .constraints_utils import CACHE_KEY_RE

_logger = logging.getLogger(__name__)


class DynamicDashboardMart(models.Model):
    _name = 'dynamic.dashboard.mart'
    _description = 'Dashboard Data Mart (ETL Lite)'
    _order = 'name, id'
    _check_company_auto = True

    _schedule_hours_positive = models.Constraint(
        'CHECK(schedule_hours IS NULL OR schedule_hours >= 1)',
        'Refresh interval must be at least 1 hour.',
    )
    _target_table_uniq = models.Constraint(
        'UNIQUE(company_id, target_table)',
        'Cache key must be unique per company.',
    )

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True,
    )
    source_type = fields.Selection([
        ('sql', 'SQL'),
        ('python', 'Python'),
    ], default='sql', required=True)
    query = fields.Text(string='SQL SELECT', help='SELECT query used to materialize rows into cache.')
    python_code = fields.Text(
        string='Python Code',
        help="Must set variable `rows` to a list of dicts. Available: env, datetime.",
    )
    target_table = fields.Char(
        string='Cache Key',
        required=True,
        help='Logical table name used as cache key (alphanumeric/underscore).',
    )
    schedule_hours = fields.Integer(string='Refresh Every (hours)', default=24)
    last_run = fields.Datetime(readonly=True)
    last_status = fields.Selection([
        ('ok', 'OK'),
        ('error', 'Error'),
        ('never', 'Never'),
    ], default='never', readonly=True)
    last_message = fields.Char(readonly=True)
    row_count = fields.Integer(readonly=True)
    cached_data = fields.Text(readonly=True, help='JSON cache of last materialization')
    external_connection_id = fields.Many2one(
        'dynamic.dashboard.connection', check_company=True,
    )
    notify_user_ids = fields.Many2many(
        'res.users',
        'dynamic_dashboard_ai_nexgen_mart_notify_user_rel',
        'mart_id',
        'user_id',
        string='Notify on Failure',
        help='Recipients notified in inbox/email when a scheduled ETL refresh fails.',
    )

    @api.constrains('target_table')
    def _check_target_table(self):
        for rec in self:
            if not CACHE_KEY_RE.match(rec.target_table or ''):
                raise ValidationError(_('Cache key must be a valid identifier (letters, numbers, underscore).'))

    @api.constrains('source_type', 'query', 'python_code')
    def _check_source_payload(self):
        for mart in self:
            if mart.source_type == 'sql' and not (mart.query or '').strip():
                raise ValidationError(
                    _('SQL SELECT is required for SQL data marts (%s).') % mart.display_name
                )
            if mart.source_type == 'python' and not (mart.python_code or '').strip():
                raise ValidationError(
                    _('Python code is required for Python data marts (%s).') % mart.display_name
                )

    def action_run_now(self):
        for mart in self:
            mart._run_etl()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('ETL'), 'message': _('Mart refresh finished.'), 'type': 'success'},
        }

    def _run_etl(self):
        self.ensure_one()
        try:
            if self.source_type == 'sql':
                rows = self._run_sql()
            else:
                rows = self._run_python()
            self.write({
                'cached_data': json.dumps(rows, default=str),
                'row_count': len(rows),
                'last_run': fields.Datetime.now(),
                'last_status': 'ok',
                'last_message': _('%s rows cached') % len(rows),
            })
        except Exception as e:
            _logger.exception('Mart ETL failed')
            self.write({
                'last_run': fields.Datetime.now(),
                'last_status': 'error',
                'last_message': str(e),
            })
            raise

    def _run_sql(self):
        Item = self.env['dynamic.dashboard.item']
        helper = Item.new({
            'query': self.query,
            'sql_row_limit': 50000,
            'data_calculation_type': 'sql',
            'external_connection_id': self.external_connection_id.id,
            'date_filter_selection': 'none',
        })
        prepared, limit, params = helper._prepare_sql_query(self.query or '', {})
        rows = helper._execute_sql_query(prepared, self.external_connection_id, params=params) or []
        return rows[:limit]

    def _run_python(self):
        import datetime
        if not self.python_code:
            raise UserError(_('Python code is empty.'))
        # Restricted locals — no builtins beyond safe_eval defaults
        loc = {
            'env': self.env,
            'datetime': datetime,
            'rows': [],
        }
        safe_eval(self.python_code, loc, mode='exec', nocopy=True)
        rows = loc.get('rows') or []
        if not isinstance(rows, list):
            raise UserError(_('Python code must set `rows` to a list.'))
        return rows

    def get_cached_rows(self):
        self.ensure_one()
        if not self.cached_data:
            self._run_etl()
        try:
            return json.loads(self.cached_data or '[]')
        except Exception:
            return []

    def fetch_as_analysis(self, result, visual, **kwargs):
        self.ensure_one()
        rows = self.get_cached_rows()
        if not rows:
            result.update({'labels': [], 'datasets': [], 'columns': [], 'records': []})
            return result
        keys = list(rows[0].keys()) if isinstance(rows[0], dict) else ['value']
        if visual == 'list':
            result.update({
                'list_view_type': 'list',
                'list_view_layout': 'layout1',
                'columns': keys,
                'column_keys': keys,
                'records': rows,
            })
            return result
        if visual in ('tile', 'kpi', 'scorecard'):
            val = list(rows[0].values())[0] if rows else 0
            result.update({'value': val, 'scorecard_values': [{'label': keys[0], 'value': val}]})
            return result
        label_key = keys[0]
        measure_keys = keys[1:] or [keys[0]]
        result.update({
            'labels': [str(r.get(label_key, '')) for r in rows],
            'datasets': [{'label': mk, 'data': [r.get(mk, 0) for r in rows]} for mk in measure_keys],
        })
        return result

    def _notify_etl_failure(self, error_message):
        self.ensure_one()
        partners = self.notify_user_ids.mapped('partner_id')
        if not partners:
            return
        subject = _('Data Mart ETL Failed: %s') % self.name
        body = Markup(
            '<p>Scheduled refresh for data mart <b>%s</b> failed.</p>'
            '<pre style="white-space:pre-wrap;background:#f8fafc;padding:8px;border-radius:6px;">%s</pre>'
        ) % (escape(self.name), escape(str(error_message)[:2000]))
        try:
            self.env['mail.thread'].message_notify(
                partner_ids=partners.ids,
                subject=subject,
                body=body,
                model=self._name,
                res_id=self.id,
                subtype_xmlid='mail.mt_note',
            )
        except Exception:
            _logger.exception('Mart failure notification failed for %s', self.name)

    @api.model
    def _cron_refresh_marts(self):
        now = fields.Datetime.now()
        for mart in self.search([('active', '=', True)]):
            hours = max(1, mart.schedule_hours or 24)
            if mart.last_run:
                delta = now - mart.last_run
                if delta.total_seconds() < hours * 3600:
                    continue
            try:
                mart._run_etl()
            except Exception as e:
                _logger.exception('Cron mart refresh failed for %s', mart.name)
                mart._notify_etl_failure(e)
        return True
