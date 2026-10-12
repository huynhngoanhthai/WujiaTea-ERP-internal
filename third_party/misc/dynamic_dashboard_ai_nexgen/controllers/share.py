# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
from odoo import http
from odoo.http import request


class DynamicDashboardShareController(http.Controller):

    @http.route('/dynamic_dashboard_ai_nexgen/share/<string:token>', type='http', auth='public', website=False)
    def share_dashboard(self, token, **kwargs):
        try:
            dashboard = request.env['dynamic.dashboard.share'].sudo().get_dashboard_by_token(token)
        except Exception as e:
            return request.make_response(str(e), status=403)
        # Redirect authenticated users into the client action; public users get a simple HTML snapshot
        if not request.env.user or request.env.user._is_public():
            items = request.env['dynamic.dashboard.item'].sudo().search([('dashboard_id', '=', dashboard.id)])
            rows = ''.join(
                f'<div style="padding:12px;margin:8px;border:1px solid #ddd;border-radius:8px;">'
                f'<b>{item.name}</b> <span style="color:#888">({item.item_type})</span></div>'
                for item in items
            )
            html = f"""<!DOCTYPE html><html><head><title>{dashboard.name}</title></head>
            <body style="font-family:sans-serif;max-width:900px;margin:40px auto;">
            <h1>{dashboard.name}</h1>
            <p>Shared dashboard preview (login for interactive view).</p>
            {rows}
            </body></html>"""
            return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])
        # Pass dashboard_id in the URL so the OWL viewer can open the shared board
        return request.redirect(
            f'/odoo/action-dynamic_dashboard_ai_nexgen.dashboard_client_action'
            f'?dashboard_id={dashboard.id}'
        )
