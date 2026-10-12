# Copyright (C) NexGen Solutions
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .constraints_utils import assert_json_object

_logger = logging.getLogger(__name__)


class DashboardConnection(models.Model):
    _name = 'dynamic.dashboard.connection'
    _description = 'Dashboard External Connection'
    _check_company_auto = True

    _port_range = models.Constraint(
        'CHECK(port IS NULL OR (port >= 1 AND port <= 65535))',
        'Port must be between 1 and 65535.',
    )

    name = fields.Char(string='Connection Name', required=True)
    connection_type = fields.Selection([
        ('postgres', 'PostgreSQL'),
        ('mysql', 'MySQL'),
        ('mssql', 'Microsoft SQL Server'),
        ('api', 'External API'),
        ('sheets', 'Google Sheets'),
    ], string='Connection Type', required=True, default='postgres')
    sheets_api_key = fields.Char(string='Google Sheets API Key')
    sheets_spreadsheet_id = fields.Char(string='Default Spreadsheet ID')
    host = fields.Char(string='Host')
    port = fields.Integer(string='Port')
    user = fields.Char(string='User')
    password = fields.Char(string='Password')
    database = fields.Char(string='Database')
    use_ssl = fields.Boolean(
        string='Use SSL',
        default=False,
        help='Require SSL/TLS for PostgreSQL (sslmode=require) or enable SSL for MySQL.',
    )
    last_test_ok = fields.Boolean(string='Last Test OK', readonly=True)
    last_test_message = fields.Char(string='Last Test Message', readonly=True)
    last_test_date = fields.Datetime(string='Last Test Date', readonly=True)

    # API Fields
    api_endpoint = fields.Char(string='API Endpoint')
    api_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
    ], string='HTTP Method', default='GET')
    api_headers = fields.Text(string='Headers (JSON)')
    api_body = fields.Text(string='Body (JSON)')
    api_data_path = fields.Char(
        string='JSON Data Path',
        help="e.g. 'data.records' if response is {'data': {'records': [...]}}",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    @api.constrains('connection_type', 'host', 'database', 'api_endpoint', 'sheets_api_key')
    def _check_connection_required_fields(self):
        for conn in self:
            ctype = conn.connection_type
            if ctype in ('postgres', 'mysql', 'mssql'):
                if not (conn.host or '').strip():
                    raise ValidationError(_('Host is required for database connections (%s).') % conn.display_name)
                if not (conn.database or '').strip():
                    raise ValidationError(_('Database name is required for database connections (%s).') % conn.display_name)
            elif ctype == 'api':
                if not (conn.api_endpoint or '').strip():
                    raise ValidationError(_('API Endpoint is required for API connections (%s).') % conn.display_name)
            elif ctype == 'sheets':
                if not (conn.sheets_api_key or '').strip():
                    raise ValidationError(
                        _('Google Sheets API Key is required for Sheets connections (%s).')
                        % conn.display_name
                    )

    @api.constrains('api_headers', 'api_body')
    def _check_api_json(self):
        for conn in self:
            assert_json_object(conn.api_headers, _('Headers (JSON)'))
            assert_json_object(conn.api_body, _('Body (JSON)'))

    def action_test_connection(self):
        self.ensure_one()
        try:
            message = self._run_connection_test()
            self.write({
                'last_test_ok': True,
                'last_test_message': message,
                'last_test_date': fields.Datetime.now(),
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection OK'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                },
            }
        except Exception as e:
            self.write({
                'last_test_ok': False,
                'last_test_message': str(e),
                'last_test_date': fields.Datetime.now(),
            })
            raise UserError(_('Connection test failed: %s') % e) from e

    def _run_connection_test(self):
        self.ensure_one()
        if self.connection_type == 'postgres':
            import psycopg2
            kwargs = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'database': self.database,
                'connect_timeout': 10,
            }
            if self.use_ssl:
                kwargs['sslmode'] = 'require'
            conn = psycopg2.connect(**kwargs)
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchone()
            finally:
                conn.close()
            return _('PostgreSQL connection successful.')

        if self.connection_type == 'mysql':
            import mysql.connector
            kwargs = {
                'host': self.host,
                'port': self.port,
                'user': self.user,
                'password': self.password,
                'database': self.database,
                'connection_timeout': 10,
            }
            if self.use_ssl:
                kwargs['ssl_disabled'] = False
            conn = mysql.connector.connect(**kwargs)
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchone()
            finally:
                conn.close()
            return _('MySQL connection successful.')

        if self.connection_type == 'mssql':
            import pymssql
            conn = pymssql.connect(
                server=self.host,
                port=str(self.port or 1433),
                user=self.user,
                password=self.password,
                database=self.database,
                login_timeout=10,
            )
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.fetchone()
            finally:
                conn.close()
            return _('Microsoft SQL Server connection successful.')

        if self.connection_type == 'sheets':
            Analysis = self.env['dynamic.dashboard.analysis']
            api_key = (
                (self.sheets_api_key or '').strip()
                or self.env['ir.config_parameter'].sudo().get_param('dynamic_dashboard_ai_nexgen.google_sheets_api_key')
            )
            if Analysis._is_placeholder_sheets_api_key(api_key):
                raise UserError(_(
                    'Replace the demo/placeholder Google Sheets API key with a real key '
                    '(Google Cloud → Credentials → API key, with Sheets API enabled).'
                ))
            return _('Google Sheets API key looks configured (live fetch not tested without Sheet ID).')

        if self.connection_type == 'api':
            import requests
            headers = {}
            if self.api_headers:
                headers = json.loads(self.api_headers)
            body = None
            if self.api_body and self.api_method == 'POST':
                body = json.loads(self.api_body)
            if self.api_method == 'POST':
                resp = requests.post(self.api_endpoint, headers=headers, json=body, timeout=15)
            else:
                resp = requests.get(self.api_endpoint, headers=headers, timeout=15)
            resp.raise_for_status()
            return _('API responded with HTTP %s.') % resp.status_code

        raise UserError(_('Unknown connection type.'))
