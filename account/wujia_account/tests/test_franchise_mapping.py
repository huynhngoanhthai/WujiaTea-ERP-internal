"""Cụm C1 — WJ-FRANCHISE-001 / WJ-FRANCHISE-002 / WJ-DEBT-006.

Gom vào `wujia_account` vì module này depend đủ `sale` + `stock` + `wujia_franchise`.
Chạy: `--test-tags wujia_franchise_map`.

⚠️ KHÔNG import `odoo.addons.account.tests.common` (freezegun cũ trong env) — dựng fixture
kế toán bằng ORM thuần trên chart đã cài sẵn, y như `wujia_portal_debt/tests`.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wujia_franchise_map')
class TestFranchiseMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        Franchise = cls.env['wujia.franchise.management']
        cls.company = cls.env.company

        cls.area_hcm = cls.env['res.area'].create({'name': 'C1 Area HCM', 'code': 'C1HCM'})
        cls.area_hn = cls.env['res.area'].create({'name': 'C1 Area HN', 'code': 'C1HN'})

        cls.partner_hcm = Partner.create({'name': 'C1 Wujia Tea — TP HCM Quận 1'})
        cls.partner_hn = Partner.create({'name': 'C1 Wujia Tea — Hà Nội Cầu Giấy'})
        cls.partner_multi = Partner.create({'name': 'C1 Partner nhiều cửa hàng'})
        cls.partner_plain = Partner.create({'name': 'C1 Nhà cung cấp thường'})

        cls.hcm = Franchise.create({
            'code': 'C1-HCM', 'name': 'C1 store HCM', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.partner_hcm.id, 'area_id': cls.area_hcm.id,
        })
        cls.hn = Franchise.create({
            'code': 'C1-HN', 'name': 'C1 store HN', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.partner_hn.id, 'area_id': cls.area_hn.id,
        })
        cls.multi_a = Franchise.create({
            'code': 'C1-M1', 'name': 'C1 multi A', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.partner_multi.id,
        })
        cls.multi_b = Franchise.create({
            'code': 'C1-M2', 'name': 'C1 multi B', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.partner_multi.id,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'C1 Trà sữa thùng', 'type': 'consu', 'list_price': 100.0,
        })
        cls.sale_journal = cls.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', cls.company.id)], limit=1)
        cls.purchase_journal = cls.env['account.journal'].search(
            [('type', '=', 'purchase'), ('company_id', '=', cls.company.id)], limit=1)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _make_so(self, partner):
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_uom_qty': 2})],
        })

    def _make_invoice(self, partner, move_type='out_invoice', journal=None):
        return self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': partner.id,
            'invoice_date': '2026-08-03',
            'journal_id': (journal or self.sale_journal).id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': 1, 'price_unit': 100.0,
            })],
        })

    # ------------------------------------------------------------------
    # WJ-FRANCHISE-001 — tự điền theo partner
    # ------------------------------------------------------------------
    def test_so_autofill_from_partner(self):
        order = self._make_so(self.partner_hcm)
        self.assertEqual(order.franchise_id, self.hcm)
        self.assertEqual(order.franchise_partner_id, self.partner_hcm)
        self.assertEqual(order.area_id, self.area_hcm)

    def test_so_recompute_on_partner_change(self):
        order = self._make_so(self.partner_hcm)
        order.partner_id = self.partner_hn
        self.assertEqual(order.franchise_id, self.hn, 'không được giữ franchise cũ')
        self.assertEqual(order.franchise_partner_id, self.partner_hn)
        self.assertEqual(order.area_id, self.area_hn)

    def test_invoice_and_picking_autofill(self):
        invoice = self._make_invoice(self.partner_hcm)
        self.assertEqual(invoice.franchise_id, self.hcm)

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_hcm.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
        })
        self.assertEqual(picking.franchise_id, self.hcm)
        self.assertEqual(picking.area_id, self.area_hcm)

    def test_multi_mapping_is_not_guessed(self):
        order = self._make_so(self.partner_multi)
        self.assertFalse(order.franchise_id, 'map nhiều cửa hàng thì không được đoán')

        draft = self.env['sale.order'].new({'partner_id': self.partner_multi.id})
        warning = draft._onchange_partner_id_franchise_warning()
        self.assertIn('warning', warning or {})
        self.assertIn('C1-M1', warning['warning']['message'])
        self.assertIn('C1-M2', warning['warning']['message'])

        # Partner map duy nhất thì im lặng (LIMIT: 0 map cũng im lặng).
        ok = self.env['sale.order'].new({'partner_id': self.partner_hcm.id})
        self.assertIsNone(ok._onchange_partner_id_franchise_warning())
        plain = self.env['sale.order'].new({'partner_id': self.partner_plain.id})
        self.assertIsNone(plain._onchange_partner_id_franchise_warning())

    def test_manual_override_is_kept(self):
        order = self._make_so(self.partner_hcm)
        order.franchise_id = self.hn
        order.invalidate_recordset()
        self.assertEqual(order.franchise_id, self.hn, 'readonly=False: kế toán sửa tay được')

    def test_child_address_falls_back_to_commercial_partner(self):
        child = self.env['res.partner'].create({
            'name': 'C1 Kho HCM', 'type': 'delivery', 'parent_id': self.partner_hcm.id,
        })
        picking = self.env['stock.picking'].create({
            'partner_id': child.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
        })
        self.assertEqual(picking.franchise_id, self.hcm)

    # ------------------------------------------------------------------
    # WJ-FRANCHISE-002 — chặn ở backend
    # ------------------------------------------------------------------
    def test_confirm_blocked_when_franchise_blank(self):
        order = self._make_so(self.partner_hcm)
        order.franchise_id = False
        with self.assertRaises(UserError) as err:
            order.action_confirm()
        msg = str(err.exception)
        self.assertIn(self.partner_hcm.name, msg)
        self.assertIn('C1-HCM', msg)
        self.assertEqual(order.state, 'draft')
        self.assertFalse(order.picking_ids, 'không được sinh chứng từ kế tiếp')

    def test_confirm_blocked_when_franchise_mismatch(self):
        order = self._make_so(self.partner_hcm)
        order.franchise_id = self.hn
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_confirm_allowed_after_fix(self):
        order = self._make_so(self.partner_hcm)
        order.franchise_id = False
        with self.assertRaises(UserError):
            order.action_confirm()
        order.franchise_id = self.hcm
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        self.assertTrue(order.picking_ids)
        self.assertEqual(order.picking_ids.franchise_id, self.hcm)

    def test_picking_validate_blocked(self):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner_hcm.id,
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
        })
        picking.franchise_id = False
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_invoice_post_blocked_then_allowed(self):
        invoice = self._make_invoice(self.partner_hcm)
        invoice.franchise_id = False
        with self.assertRaises(UserError):
            invoice.action_post()
        self.assertEqual(invoice.state, 'draft')
        invoice.franchise_id = self.hcm
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    def test_vendor_bill_not_blocked(self):
        bill = self._make_invoice(
            self.partner_plain, move_type='in_invoice', journal=self.purchase_journal)
        self.assertFalse(bill.franchise_id)
        bill.action_post()
        self.assertEqual(bill.state, 'posted', 'partner không map thì không được chặn')

    # ------------------------------------------------------------------
    # WJ-DEBT-006 — credit note kế thừa cửa hàng
    # ------------------------------------------------------------------
    def _reversal_wizard(self, invoice):
        return self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({
            'journal_id': invoice.journal_id.id,
            'reason': 'C1 test',
        })

    def test_credit_note_inherits_franchise(self):
        invoice = self._make_invoice(self.partner_hcm)
        invoice.action_post()
        wizard = self._reversal_wizard(invoice)
        wizard.refund_moves()
        credit = wizard.new_move_ids
        self.assertEqual(credit.move_type, 'out_refund')
        self.assertEqual(credit.franchise_id, self.hcm, 'bản nháp phải có sẵn cửa hàng')
        credit.action_post()
        self.assertEqual(credit.franchise_id, self.hcm, 'giữ nguyên sau khi ghi sổ')

    def test_modify_reversal_inherits_franchise(self):
        invoice = self._make_invoice(self.partner_hcm)
        invoice.action_post()
        wizard = self._reversal_wizard(invoice)
        wizard.modify_moves()
        for move in wizard.new_move_ids:
            self.assertEqual(move.franchise_id, self.hcm)

    def test_portal_scope_sees_credit_note(self):
        invoice = self._make_invoice(self.partner_hcm)
        invoice.action_post()
        wizard = self._reversal_wizard(invoice)
        wizard.refund_moves()
        credit = wizard.new_move_ids
        credit.action_post()

        Move = self.env['account.move']
        self.assertIn(credit, Move.search([('franchise_id', '=', self.hcm.id)]))
        self.assertNotIn(credit, Move.search([('franchise_id', '=', self.hn.id)]))
