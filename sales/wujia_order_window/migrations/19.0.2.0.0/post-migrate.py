import logging

_logger = logging.getLogger(__name__)

DEFAULT_TZ = 'Asia/Ho_Chi_Minh'


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'wujia_order_window' AND column_name = 'area_id'
    """)
    if cr.fetchone():
        cr.execute("SELECT count(*) FROM wujia_order_window WHERE area_id IS NOT NULL")
        before = cr.fetchone()[0]
        cr.execute("""
            INSERT INTO wujia_order_window_res_area_rel (window_id, area_id)
            SELECT id, area_id FROM wujia_order_window WHERE area_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        cr.execute("""
            SELECT count(*) FROM wujia_order_window w
              JOIN wujia_order_window_res_area_rel r ON r.window_id = w.id AND r.area_id = w.area_id
        """)
        after = cr.fetchone()[0]
        _logger.info("wujia_order_window: area_id -> area_ids %s/%s", after, before)
        if after != before:
            raise RuntimeError("wujia_order_window: area_id migration lost rows (%s/%s)" % (after, before))

    cr.execute("""
        UPDATE res_partner p SET tz = %s
          FROM wujia_franchise_management f
         WHERE f.partner_id = p.id AND (p.tz IS NULL OR p.tz = '')
     RETURNING p.id
    """, (DEFAULT_TZ,))
    _logger.info("wujia_order_window: store timezone %s set on %s partners", DEFAULT_TZ, cr.rowcount)
