# -*- coding: utf-8 -*-
import time
import logging
from odoo import http, fields, _
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    import jwt
except ImportError:
    jwt = None


class MetabaseEmbedController(http.Controller):

    @http.route('/metabase/embed/<int:dashboard_id>', type='http', auth='user', website=False)
    def embed_dashboard(self, dashboard_id, **kwargs):
        dashboard = request.env['metabase.dashboard'].sudo().browse(int(dashboard_id))
        if not dashboard.exists() or not dashboard.active:
            return request.not_found()

        user = request.env.user

        # 1. Check company permissions
        current_company = request.env.company
        if dashboard.company_ids and current_company not in dashboard.company_ids:
            return request.render('wujia_metabase_connector.embed_error_page', {
                'error_title': _("Access Denied"),
                'error_message': _("This dashboard is not available for your current company (%s).", current_company.name)
            })

        if dashboard.instance_id.company_ids and current_company not in dashboard.instance_id.company_ids:
            return request.render('wujia_metabase_connector.embed_error_page', {
                'error_title': _("Access Denied"),
                'error_message': _("The Metabase instance is not configured for your current company (%s).", current_company.name)
            })

        # 2. Check security group permissions
        if dashboard.group_ids:
            has_group = any(user.has_group(g.xml_id) for g in dashboard.group_ids if g.xml_id)
            if not has_group and not user.has_group('base.group_system'):
                return request.render('wujia_metabase_connector.embed_error_page', {
                    'error_title': _("Access Denied"),
                    'error_message': _("You do not have permission to view this Metabase Dashboard.")
                })

        instance = dashboard.instance_id
        if not instance or not instance.active:
            return request.render('wujia_metabase_connector.embed_error_page', {
                'error_title': _("Configuration Error"),
                'error_message': _("The Metabase BI Instance is inactive or not configured.")
            })

        if not jwt:
            return request.render('wujia_metabase_connector.embed_error_page', {
                'error_title': _("System Error"),
                'error_message': _("Python 'PyJWT' library is not installed on the server.")
            })

        base_url = instance.base_url.strip().rstrip('/')
        secret_key = instance.embedding_secret.strip()
        expiry_mins = instance.token_expiry_minutes or 10

        now = round(time.time())
        payload = {
            "resource": {"dashboard": dashboard.dashboard_id},
            "params": {},
            "iat": now,
            "exp": now + (expiry_mins * 60),
        }

        try:
            token = jwt.encode(payload, secret_key, algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode('utf-8')
        except Exception as e:
            _logger.error("Failed to generate Metabase JWT token: %s", str(e))
            return request.render('wujia_metabase_connector.embed_error_page', {
                'error_title': _("JWT Generation Error"),
                'error_message': _("Failed to sign JWT token: %s", str(e))
            })

        bordered_str = "false"
        titled_str = "false" if not dashboard.description else "true"
        embed_url = f"{base_url}/embed/dashboard/{token}#bordered={bordered_str}&titled={titled_str}"

        values = {
            'dashboard': dashboard,
            'embed_url': embed_url,
            'height': dashboard.height or 800,
        }
        return request.render('wujia_metabase_connector.embed_iframe_page', values)

    @http.route('/metabase/embed_url/<int:dashboard_id>', type='http', auth='user', website=False)
    def embed_dashboard_url(self, dashboard_id, **kwargs):
        dashboard = request.env['metabase.dashboard'].sudo().browse(int(dashboard_id))
        if not dashboard.exists() or not dashboard.active:
            return request.make_json_response({
                'status': 'error',
                'error_title': _("Not Found"),
                'error_message': _("Dashboard not found or inactive.")
            })

        user = request.env.user
        current_company = request.env.company

        if dashboard.company_ids and current_company not in dashboard.company_ids:
            return request.make_json_response({
                'status': 'error',
                'error_title': _("Access Denied"),
                'error_message': _("This dashboard is not available for your current company (%s).", current_company.name)
            })

        if dashboard.instance_id.company_ids and current_company not in dashboard.instance_id.company_ids:
            return request.make_json_response({
                'status': 'error',
                'error_title': _("Access Denied"),
                'error_message': _("The Metabase instance is not configured for your current company (%s).", current_company.name)
            })

        if dashboard.group_ids:
            has_group = any(user.has_group(g.xml_id) for g in dashboard.group_ids if g.xml_id)
            if not has_group and not user.has_group('base.group_system'):
                return request.make_json_response({
                    'status': 'error',
                    'error_title': _("Access Denied"),
                    'error_message': _("You do not have permission to view this Metabase Dashboard.")
                })

        instance = dashboard.instance_id
        if not instance or not instance.active:
            return request.make_json_response({
                'status': 'error',
                'error_title': _("Configuration Error"),
                'error_message': _("The Metabase BI Instance is inactive or not configured.")
            })

        if not jwt:
            return request.make_json_response({
                'status': 'error',
                'error_title': _("System Error"),
                'error_message': _("Python 'PyJWT' library is not installed on the server.")
            })

        base_url = instance.base_url.strip().rstrip('/')
        secret_key = instance.embedding_secret.strip()
        expiry_mins = instance.token_expiry_minutes or 10

        now = round(time.time())
        payload = {
            "resource": {"dashboard": dashboard.dashboard_id},
            "params": {},
            "iat": now,
            "exp": now + (expiry_mins * 60),
        }

        try:
            token = jwt.encode(payload, secret_key, algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode('utf-8')
        except Exception as e:
            _logger.error("Failed to generate Metabase JWT token: %s", str(e))
            return request.make_json_response({
                'status': 'error',
                'error_title': _("JWT Generation Error"),
                'error_message': _("Failed to sign JWT token: %s", str(e))
            })

        bordered_str = "false"
        titled_str = "false" if not dashboard.description else "true"
        embed_url = f"{base_url}/embed/dashboard/{token}#bordered={bordered_str}&titled={titled_str}"

        return request.make_json_response({
            'status': 'success',
            'embed_url': embed_url,
        })
