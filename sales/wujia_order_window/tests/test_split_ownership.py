"""Sau khi tách: module cũ không còn sở hữu gì; hook chỉ đổi đúng phần được giao; helper suy đủ danh sách."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_core.tools.module_split import imd_names, migrate_ownership
from odoo.addons.wujia_order_window.hooks import NEW_MODULE, OLD_MODULE

FAKE_OLD = 'wujia_test_fake_old'


@tagged('post_install', '-at_install', 'wujia_order_window')
class TestSplitOwnership(TransactionCase):

    def owner_of(self, table, name):
        self.env.cr.execute(f"""SELECT m.name FROM {table} t JOIN ir_module_module m ON m.id = t.module
                                 WHERE t.name = %s""", (name,))
        return self.env.cr.fetchone()[0]

    def test_old_module_owns_nothing(self):
        cr = self.env.cr
        cr.execute("SELECT count(*) FROM ir_model_data WHERE module = %s", (OLD_MODULE,))
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("""SELECT DISTINCT m.name FROM ir_model_constraint c
                        JOIN ir_module_module m ON m.id = c.module
                        JOIN ir_model im ON im.id = c.model WHERE im.model = 'wujia.order.window'""")
        self.assertEqual([r[0] for r in cr.fetchall()], [NEW_MODULE])
        for xmlid in ('model_wujia_order_window', 'menu_wujia_order_window', 'action_wujia_order_window',
                      'access_wujia_order_window_user', 'field_res_config_settings__portal_order_time_from'):
            self.assertTrue(self.env.ref(f'{NEW_MODULE}.{xmlid}', raise_if_not_found=False), xmlid)

    def test_imd_names_covers_everything_the_pilot_moved(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s ORDER BY name", (NEW_MODULE,))
        everything = [r[0] for r in cr.fetchall()]
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s AND model = 'ir.ui.menu'", (NEW_MODULE,))
        menus = [r[0] for r in cr.fetchall()]
        by_model = imd_names(cr, NEW_MODULE, ['wujia.order.window', 'res.config.settings', 'sale.order', 'wujia.franchise.management'])
        self.assertEqual(sorted(set(everything) - set(by_model)), sorted(menus), 'chỉ menu là phải liệt kê tay')
        self.assertEqual(imd_names(cr, NEW_MODULE, ['wujia.order.window', 'res.config.settings', 'sale.order', 'wujia.franchise.management'],
                                   extra=menus), everything)
        self.assertEqual(imd_names(cr, NEW_MODULE, ['sale.order']),
                         ['field_sale_order__display_name', 'field_sale_order__id', 'model_sale_order'])

    def test_migrate_moves_only_named_rows_and_models(self):
        # Không tra module vỏ: nó đã rời repo nên DB trắng không có dòng ir_module_module.
        cr, Imd = self.env.cr, self.env['ir.model.data']
        cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, 'uninstalled') RETURNING id", (FAKE_OLD,))
        old_id = cr.fetchone()[0]
        partner = self.env['res.partner'].create({'name': 'F7 probe'})
        for name in ('f7_moved', 'f7_kept'):
            Imd.create({'module': FAKE_OLD, 'name': name, 'model': 'res.partner', 'res_id': partner.id})
        for cname, model in (('f7_cons_window', 'wujia.order.window'), ('f7_cons_partner', 'res.partner')):
            cr.execute("""INSERT INTO ir_model_constraint (name, module, model, type)
                          VALUES (%s, %s, (SELECT id FROM ir_model WHERE model = %s), 'u')""",
                       (cname, old_id, model))

        moved = migrate_ownership(cr, FAKE_OLD, NEW_MODULE, names=['f7_moved'], models=['wujia.order.window'])

        self.assertEqual(moved, {'ir_model_data': 1, 'ir_model_constraint': 1, 'ir_model_relation': 0})
        self.assertTrue(self.env.ref(f'{NEW_MODULE}.f7_moved', raise_if_not_found=False))
        self.assertTrue(self.env.ref(f'{FAKE_OLD}.f7_kept', raise_if_not_found=False))
        self.assertEqual(self.owner_of('ir_model_constraint', 'f7_cons_window'), NEW_MODULE)
        self.assertEqual(self.owner_of('ir_model_constraint', 'f7_cons_partner'), FAKE_OLD)

        moved = migrate_ownership(cr, FAKE_OLD, NEW_MODULE)
        self.assertEqual((moved['ir_model_data'], moved['ir_model_constraint']), (1, 1))
        self.assertEqual(self.owner_of('ir_model_constraint', 'f7_cons_partner'), NEW_MODULE)

        with self.assertRaises(ValueError):
            migrate_ownership(cr, FAKE_OLD, 'wujia_module_khong_ton_tai')
