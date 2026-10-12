# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
def post_init_hook(env):
    """Migrate deprecated Gemini model ids and dashboard categories."""
    ICP = env['ir.config_parameter'].sudo()
    deprecated = {
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash-001',
        'gemini-1.5-pro',
        'gemini-1.5-pro-latest',
        'gemini-2.0-flash',
        'gemini-2.0-flash-001',
        'gemini-2.0-flash-lite',
        'gemini-2.0-flash-lite-001',
        'gemini-pro',
        'gemini-pro-vision',
    }
    current = (ICP.get_param('dynamic_dashboard_ai_nexgen.gemini_model') or '').strip().removeprefix('models/')
    if not current or current in deprecated:
        ICP.set_param('dynamic_dashboard_ai_nexgen.gemini_model', 'gemini-3.5-flash')

    # Link legacy category Char values to dynamic.dashboard.category records
    Category = env['dynamic.dashboard.category'].sudo()
    Dashboard = env['dynamic.dashboard'].sudo()
    for dash in Dashboard.search([('category', '!=', False), ('category_id', '=', False)]):
        dash.category_id = Category.get_or_create(dash.category)
