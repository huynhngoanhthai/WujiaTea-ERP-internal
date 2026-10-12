# Copyright (C) NexGen Solutions
def migrate(cr, version):
    """Hide horizontal zoom bar by default on existing chart items."""
    cr.execute("""
        UPDATE dynamic_dashboard_ai_nexgen_item
           SET show_scrollbar_x = false
         WHERE show_scrollbar_x IS TRUE
    """)
