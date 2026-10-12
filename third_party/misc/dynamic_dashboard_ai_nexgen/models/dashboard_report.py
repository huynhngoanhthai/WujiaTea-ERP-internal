# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup, escape

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DynamicDashboardReport(models.Model):
    _name = 'dynamic.dashboard.report'
    _description = 'Dashboard Email Report'
    _order = 'next_execution_date, id'
    _check_company_auto = True

    _interval_number_positive = models.Constraint(
        'CHECK(interval_number >= 1)',
        'Report interval number must be at least 1.',
    )

    name = fields.Char(string='Report Name', required=True, translate=True)
    dashboard_id = fields.Many2one(
        'dynamic.dashboard', string='Dashboard', required=True, ondelete='cascade',
        check_company=True,
    )
    user_ids = fields.Many2many(
        'res.users',
        string='Recipients',
    )
    interval_number = fields.Integer(string='Interval Number', default=1, required=True)
    interval_type = fields.Selection([
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], string='Interval Unit', default='days', required=True)
    next_execution_date = fields.Datetime(
        string='Next Execution Date',
        default=fields.Datetime.now,
        required=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='dashboard_id.company_id', store=True,
    )
    date_filter = fields.Selection([
        ('none', 'None (All Time)'),
        ('today', 'Today'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('this_quarter', 'This Quarter'),
        ('this_year', 'This Year'),
        ('last_7_days', 'Last 7 Days'),
        ('last_30_days', 'Last 30 Days'),
        ('last_90_days', 'Last 90 Days'),
        ('month_to_date', 'Month to Date'),
        ('year_to_date', 'Year to Date'),
    ], string='Data Date Filter', default='none',
        help='Optional date filter applied when collecting KPI/tile values for the email.',
    )
    include_charts = fields.Boolean(
        string='Include Chart Summaries',
        default=True,
        help='Add label/value summaries for chart widgets in the email body.',
    )
    last_sent_date = fields.Datetime(string='Last Sent', readonly=True)
    last_status = fields.Selection([
        ('ok', 'OK'),
        ('error', 'Error'),
        ('never', 'Never'),
    ], string='Last Status', default='never', readonly=True)
    last_error = fields.Text(string='Last Error', readonly=True)

    def _get_interval_delta(self):
        self.ensure_one()
        n = max(1, self.interval_number or 1)
        if self.interval_type == 'hours':
            return timedelta(hours=n)
        if self.interval_type == 'weeks':
            return timedelta(weeks=n)
        if self.interval_type == 'months':
            return relativedelta(months=n)
        return timedelta(days=n)

    def _advance_next_execution(self):
        """Move next_execution forward past now by one or more intervals."""
        self.ensure_one()
        now = fields.Datetime.now()
        nxt = self.next_execution_date or now
        delta = self._get_interval_delta()
        # Always move at least one step after a due run; catch up if overdue
        if nxt > now:
            nxt = nxt + delta
        else:
            # Guard against tight loops on bad interval
            for _ in range(10000):
                nxt = nxt + delta
                if nxt > now:
                    break
        self.next_execution_date = nxt

    def _format_value(self, value):
        if value is None:
            return '—'
        if isinstance(value, float):
            return f'{value:,.2f}'
        if isinstance(value, (int,)):
            return f'{value:,}'
        return str(value)

    def _build_report_body(self):
        """Build HTML summary of dashboard items for email."""
        self.ensure_one()
        dashboard = self.dashboard_id
        Item = self.env['dynamic.dashboard.item']
        date_filter = self.date_filter or 'none'

        rows_kpi = []
        rows_chart = []
        errors = []

        for item in dashboard.item_ids.sorted(lambda i: (i.grid_y, i.grid_x, i.id)):
            try:
                data = Item.fetch_item_data(
                    item.id,
                    global_date_filter=date_filter,
                ) or {}
            except Exception as e:
                _logger.exception('Report fetch failed for item %s', item.id)
                errors.append((item.name, str(e)))
                continue

            if data.get('error'):
                errors.append((item.name, data['error']))
                continue

            if item.item_type in ('tile', 'kpi', 'scorecard', 'todo'):
                val = data.get('value')
                if val is None and data.get('scorecard_values'):
                    parts = [
                        Markup('%s: %s') % (
                            escape(sv.get('label') or ''),
                            escape(self._format_value(sv.get('value'))),
                        )
                        for sv in data['scorecard_values'][:8]
                    ]
                    rows_kpi.append((
                        item.name,
                        item.item_type,
                        Markup('<br/>').join(parts) if parts else Markup('—'),
                    ))
                else:
                    extra = ''
                    if data.get('compare') is not None or data.get('delta_pct') is not None:
                        delta = data.get('delta_pct')
                        if delta is not None:
                            extra = f' ({delta:+.1f}%)'
                    rows_kpi.append((
                        item.name,
                        item.item_type,
                        f"{self._format_value(val)}{extra}",
                    ))
            elif self.include_charts and item.item_type not in (
                'list', 'iframe', 'odoo_view', 'todo', 'text', 'image',
            ):
                labels = data.get('labels') or []
                datasets = data.get('datasets') or []
                if labels and datasets:
                    series = datasets[0]
                    values = series.get('data') or []
                    pairs = []
                    for label, value in list(zip(labels, values))[:12]:
                        pairs.append(Markup(
                            '<tr><td style="padding:2px 8px;">%(label)s</td>'
                            '<td style="padding:2px 8px;text-align:right;">%(value)s</td></tr>'
                        ) % {
                            'label': escape(str(label)),
                            'value': escape(self._format_value(value)),
                        })
                    if len(labels) > 12:
                        pairs.append(Markup(
                            '<tr><td colspan="2" style="padding:4px 8px;color:#888;">… +%s more</td></tr>'
                        ) % (len(labels) - 12))
                    table = Markup(
                        '<table style="border-collapse:collapse;font-size:13px;">%s</table>'
                    ) % Markup('').join(pairs)
                    rows_chart.append((item.name, item.item_type, table))

        def section(title, rows):
            if not rows:
                return Markup('')
            lis = []
            for name, itype, value in rows:
                cell = value if isinstance(value, Markup) else escape(str(value))
                lis.append(Markup(
                    '<tr>'
                    '<td style="padding:8px 12px;border-bottom:1px solid #eee;">'
                    '<b>%(name)s</b>'
                    '<div style="color:#888;font-size:11px;">%(itype)s</div></td>'
                    '<td style="padding:8px 12px;border-bottom:1px solid #eee;">%(val)s</td>'
                    '</tr>'
                ) % {
                    'name': escape(name or ''),
                    'itype': escape(itype or ''),
                    'val': cell,
                })
            return Markup(
                '<h3 style="margin:24px 0 8px;color:#2b3674;">%(title)s</h3>'
                '<table style="width:100%;border-collapse:collapse;background:#fff;'
                'border:1px solid #e5e7eb;border-radius:8px;">%(rows)s</table>'
            ) % {
                'title': escape(title),
                'rows': Markup('').join(lis),
            }

        err_html = Markup('')
        if errors:
            err_items = Markup('').join(
                Markup('<li><b>%s</b>: %s</li>') % (escape(n or ''), escape(e or ''))
                for n, e in errors[:10]
            )
            err_html = Markup(
                '<div style="margin-top:16px;padding:12px;background:#fff7ed;border:1px solid #fed7aa;'
                'border-radius:8px;"><b>Some widgets could not be loaded:</b><ul>%s</ul></div>'
            ) % err_items

        filter_label = dict(self._fields['date_filter'].selection).get(date_filter, date_filter)
        try:
            from .l10n_utils import date_filter_label
            filter_label = date_filter_label(date_filter)
        except Exception:
            pass
        sent_at = fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M')

        header = Markup(
            '<div style="font-family:Arial,Helvetica,sans-serif;color:#1f2937;max-width:720px;">'
            '<h2 style="margin:0 0 4px;color:#4318FF;">%(dash)s</h2>'
            '<p style="margin:0 0 16px;color:#6b7280;">'
            'Automated report <b>%(report)s</b> · Filter: %(filt)s · Generated %(when)s'
            '</p>'
        ) % {
            'dash': escape(dashboard.name or ''),
            'report': escape(self.name or ''),
            'filt': escape(filter_label or ''),
            'when': escape(sent_at),
        }
        footer = Markup(
            '<p style="margin-top:24px;font-size:12px;color:#9ca3af;">'
            'Sent by Dynamic Dashboard. Open Odoo to explore the full interactive dashboard.'
            '</p></div>'
        )
        return header + section('KPIs & Tiles', rows_kpi) + section('Chart Summaries', rows_chart) + (
            err_html or Markup('')
        ) + footer

    def _recipient_partners(self):
        self.ensure_one()
        partners = self.user_ids.mapped('partner_id').filtered(lambda p: p.email)
        return partners

    def action_send_report(self):
        """Send report email(s) immediately (used by UI and cron)."""
        for report in self:
            report._send_report_email(raise_on_error=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dashboard Report'),
                'message': _('Report email(s) sent.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def _send_report_email(self, raise_on_error=False):
        self.ensure_one()
        if not self.dashboard_id or not self.dashboard_id.active:
            msg = _('Dashboard is missing or archived.')
            self.write({'last_status': 'error', 'last_error': msg})
            if raise_on_error:
                raise UserError(msg)
            return False

        partners = self._recipient_partners()
        if not partners:
            msg = _('No recipients with a valid email address.')
            self.write({'last_status': 'error', 'last_error': msg})
            if raise_on_error:
                raise UserError(msg)
            _logger.warning('Dashboard report %s skipped: %s', self.id, msg)
            return False

        try:
            body = self._build_report_body()
            subject = _('Dashboard Report: %s') % self.dashboard_id.name
            mail = self.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body,
                'recipient_ids': [(6, 0, partners.ids)],
                'auto_delete': True,
                'model': 'dynamic.dashboard',
                'res_id': self.dashboard_id.id,
            })
            mail.send()

            self.write({
                'last_sent_date': fields.Datetime.now(),
                'last_status': 'ok',
                'last_error': False,
            })
            # Chatter note on the dashboard
            self.dashboard_id.message_post(
                body=Markup(
                    _('Scheduled report <b>%s</b> emailed to %s.')
                ) % (
                    escape(self.name),
                    escape(', '.join(partners.mapped('name'))),
                ),
                subtype_xmlid='mail.mt_note',
                message_type='notification',
            )
            # Inbox notifications for recipients
            self.dashboard_id.message_notify(
                partner_ids=partners.ids,
                subject=subject,
                body=Markup(
                    _('Your scheduled dashboard report <b>%s</b> has been sent by email.')
                ) % escape(self.name),
                subtype_xmlid='mail.mt_note',
            )
            return True
        except Exception as e:
            _logger.exception('Failed to send dashboard report %s', self.id)
            self.write({
                'last_status': 'error',
                'last_error': str(e),
            })
            if raise_on_error:
                raise
            return False

    @api.model
    def _cron_send_reports(self):
        now = fields.Datetime.now()
        reports = self.search([
            ('active', '=', True),
            ('next_execution_date', '<=', now),
            ('dashboard_id.active', '=', True),
        ])
        for report in reports:
            try:
                report._send_report_email(raise_on_error=False)
            finally:
                # Always advance schedule so a failing report does not retry every cron tick forever
                try:
                    report._advance_next_execution()
                except Exception:
                    _logger.exception('Failed to advance next_execution for report %s', report.id)
        return True
