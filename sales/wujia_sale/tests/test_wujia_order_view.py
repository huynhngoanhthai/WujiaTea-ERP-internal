# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests.common import TransactionCase, tagged

# Thứ tự 13 cột BA chốt 08/09/2026 (cột 14 "Tuyến cung ứng" chờ field, xem LIMIT)
EXPECTED_COLUMNS = [
    'name', 'create_date', 'date_order', 'franchise_id', 'area_id', 'partner_id',
    'is_portal_order', 'is_return_order', 'warehouse_id', 'total_planned_weight',
    'batch_id', 'amount_total', 'state',
]
WUJIA_FIELDS = [
    'franchise_id', 'area_id', 'is_portal_order', 'is_return_order',
    'total_planned_weight', 'batch_id',
]


def visible_columns(arch, company_id=None):
    """Cột người dùng thực sự thấy: bỏ column_invisible và optional=hide."""
    root = etree.fromstring(arch)
    names = []
    for node in root.xpath('//list/field'):
        if node.get('column_invisible') in ('True', '1'):
            continue
        if node.get('optional') == 'hide':
            continue
        name = node.get('name')
        if name == 'company_id':  # chỉ hiện ở DB multi-company, không thuộc 13 cột BA
            continue
        names.append(name)
    return names


@tagged('post_install', '-at_install', 'wujia_sale')
class TestWujiaOrderView(TransactionCase):
    """WJ-SALE-002 (STT 138) — danh sách "Đơn hàng Ngô Gia"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SaleOrder = cls.env['sale.order']
        # Đơn portal bị chặn ngoài khung giờ (wujia_order_window) ⇒ test lọc không phụ thuộc giờ chạy.
        cls.env['ir.config_parameter'].sudo().set_param(
            'wujia_portal.portal_order_time_limit_enabled', 'False')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Store Partner WJ-SALE-002',
            'is_franchise': True,
        })
        cls.franchise = cls.env['wujia.franchise.management'].create({
            'code': 'TEST-002',
            'name': 'Test Franchise Store WJ-SALE-002',
            'partner_id': cls.partner.id,
        })

    def test_01_action_and_menu(self):
        """Action/menu riêng, trỏ đúng list view Wujia và search view Wujia."""
        action = self.env.ref('wujia_sale.action_wujia_sale_orders')
        self.assertEqual(action.res_model, 'sale.order')
        self.assertEqual(
            action.search_view_id.id,
            self.env.ref('wujia_sale.view_sales_order_filter_wujia').id,
            "Action phải dùng search view riêng, không dùng bộ lọc SO chuẩn",
        )
        list_views = action.view_ids.filtered(lambda v: v.view_mode == 'list')
        self.assertEqual(
            list_views.view_id.id,
            self.env.ref('wujia_sale.view_order_tree_wujia').id,
            "Action phải mở đúng list view riêng",
        )

        menu = self.env.ref('wujia_sale.menu_wujia_sale_orders')
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(menu.parent_id.id, self.env.ref('sale.sale_order_menu').id)
        self.assertEqual(menu.sequence, 2)

    def test_02_view_is_primary_inherit(self):
        """Kế thừa sale.sale_order_tree nhưng mode=primary ⇒ cô lập."""
        tree_view = self.env.ref('wujia_sale.view_order_tree_wujia')
        self.assertEqual(tree_view.mode, 'primary')
        self.assertEqual(tree_view.priority, 99)
        self.assertEqual(tree_view.inherit_id.id, self.env.ref('sale.sale_order_tree').id)

        search_view = self.env.ref('wujia_sale.view_sales_order_filter_wujia')
        self.assertEqual(search_view.mode, 'primary')
        self.assertEqual(
            search_view.inherit_id.id, self.env.ref('sale.view_sales_order_filter').id)

    def test_03_standard_views_untouched(self):
        """Tiêu chí 1 + 9: view/action SO chuẩn không mang field Wujia."""
        for xml_id in ('sale.sale_order_tree', 'sale.view_order_tree'):
            view = self.env.ref(xml_id)
            arch = self.SaleOrder.get_view(view_id=view.id, view_type='list')['arch']
            names = [f.get('name') for f in etree.fromstring(arch).xpath('//field')]
            for fname in WUJIA_FIELDS:
                self.assertNotIn(fname, names, f"{xml_id} bị lây field '{fname}'")

        default_arch = self.SaleOrder.get_view(view_type='list')['arch']
        default_names = [
            f.get('name') for f in etree.fromstring(default_arch).xpath('//field')]
        for fname in WUJIA_FIELDS:
            self.assertNotIn(fname, default_names, "List view mặc định bị lây field Wujia")

        std_search = self.env.ref('sale.view_sales_order_filter')
        search_arch = self.SaleOrder.get_view(
            view_id=std_search.id, view_type='search')['arch']
        filter_names = [
            f.get('name') for f in etree.fromstring(search_arch).xpath('//filter')]
        self.assertNotIn('filter_portal_only', filter_names,
                         "Bộ lọc SO chuẩn bị lây filter Wujia")

    def test_04_wujia_list_columns_and_order(self):
        """Tiêu chí 2 + 3 + 4: đúng cột, đúng thứ tự, nhãn ngày, cột chuẩn bị ẩn."""
        view = self.env.ref('wujia_sale.view_order_tree_wujia')
        arch = self.SaleOrder.get_view(view_id=view.id, view_type='list')['arch']
        self.assertEqual(visible_columns(arch), EXPECTED_COLUMNS)

        root = etree.fromstring(arch)
        create_date = root.xpath("//list/field[@name='create_date']")[0]
        self.assertEqual(create_date.get('string'), 'Order Date')
        self.assertEqual(create_date.get('readonly'), '1')
        self.assertEqual(
            root.xpath("//list/field[@name='date_order']")[0].get('string'),
            'Confirmation Date')

        for fname in ('user_id', 'activity_ids', 'team_id', 'tag_ids',
                      'invoice_status', 'commitment_date', 'expected_date'):
            node = root.xpath(f"//list/field[@name='{fname}']")
            self.assertTrue(node, f"Field '{fname}' phải còn trong view (không xoá khỏi model)")
            self.assertEqual(node[0].get('optional'), 'hide',
                             f"Field '{fname}' phải optional=hide")

        # Tiêu chí 8: tổng tiền monetary cần currency_id, đơn huỷ giữ decoration chuẩn
        self.assertTrue(root.xpath("//list/field[@name='currency_id']"))
        self.assertEqual(root.xpath('//list')[0].get('decoration-muted'), "state == 'cancel'")

    def test_05_search_filters_and_group_by(self):
        """Tiêu chí 7: filter/group by dùng field + domain thật."""
        view = self.env.ref('wujia_sale.view_sales_order_filter_wujia')
        arch = self.SaleOrder.get_view(view_id=view.id, view_type='search')['arch']
        root = etree.fromstring(arch)

        domains = {f.get('name'): f.get('domain') for f in root.xpath('//filter')
                   if f.get('domain')}
        self.assertEqual(domains.get('filter_no_batch'), "[('batch_id', '=', False)]")
        self.assertIn('filter_portal_only', domains)
        self.assertIn('filter_return_order', domains)
        self.assertIn('filter_manual_order', domains)
        for name in ('filter_state_draft', 'filter_state_sent',
                     'filter_state_sale', 'filter_state_cancel'):
            self.assertIn(name, domains)

        contexts = " ".join(f.get('context') for f in root.xpath('//filter')
                            if f.get('context'))
        for key in ("'franchise_id'", "'area_id'", "'state'", "'warehouse_id'",
                    "'batch_id'"):
            self.assertIn(key, contexts)

        search_fields = [f.get('name') for f in root.xpath('//search/field')]
        for fname in ('franchise_id', 'batch_id', 'warehouse_id'):
            self.assertIn(fname, search_fields)

    def test_06_filters_return_right_orders(self):
        """Tiêu chí 7 + 10: 3 nguồn đơn tách đúng, 'chưa có Batch' chỉ ra batch rỗng."""
        common = {'partner_id': self.partner.id, 'franchise_id': self.franchise.id}
        so_portal = self.SaleOrder.create(
            dict(common, is_portal_order=True, is_return_order=False))
        so_return = self.SaleOrder.create(
            dict(common, is_portal_order=False, is_return_order=True))
        so_manual = self.SaleOrder.create(
            dict(common, is_portal_order=False, is_return_order=False))

        portal = self.SaleOrder.search([('is_portal_order', '=', True)])
        self.assertIn(so_portal, portal)
        self.assertNotIn(so_return, portal)
        self.assertNotIn(so_manual, portal)

        manual = self.SaleOrder.search([
            ('is_portal_order', '=', False), ('is_return_order', '=', False)])
        self.assertIn(so_manual, manual)
        self.assertNotIn(so_portal, manual)

        no_batch = self.SaleOrder.search([('batch_id', '=', False)])
        self.assertFalse(no_batch.filtered('batch_id'))
        self.assertIn(so_manual, no_batch)
