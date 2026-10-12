def migrate(cr, version):
    """`state` becomes date-driven; `is_cancelled` is now the only manual lever, so the
    cancellation recorded in the old `state` column must survive the recompute."""
    cr.execute("ALTER TABLE wujia_franchise_contract ADD COLUMN IF NOT EXISTS is_cancelled boolean")
    cr.execute("UPDATE wujia_franchise_contract SET is_cancelled = (state = 'cancelled') WHERE is_cancelled IS NULL")
