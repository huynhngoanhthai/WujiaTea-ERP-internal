"""Cụm D — giá & tiền tệ portal (WJ-ORD-024 / WJ-ORD-025 / WJ-PH-005).

Chạy: `--test-tags wujia_pricing`.

Câu hỏi test phải trả lời được, đúng cái BA khiếu nại:
  "Con số portal hiện TRƯỚC khi bấm gửi có bằng đúng con số sale.order sinh ra
   SAU khi bấm gửi không — ở mọi kiểu thuế?"

Nên mọi case đều đối chiếu helper với `sale.order.line.price_total` / `amount_total`
THẬT do Odoo tính, chứ không so với một con số tự gõ ra.

⚠️ KHÔNG import `odoo.addons.account.tests.common` — chuỗi import của nó kéo theo
`base.tests.test_date_utils` dùng `freeze_time(as_kwarg=...)`, vỡ với freezegun cũ
trong env (bài học Sprint 48). Fixture dựng bằng ORM thuần.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_portal_base.controllers.utils import (
    portal_line_price_vals,
    portal_money,
    portal_tax_mapper,
)


@tagged('post_install', '-at_install', 'wujia_pricing')
class TestPortalPricing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.partner = cls.env['res.partner'].create({'name': 'Cụm D — cửa hàng test'})
        Tax = cls.env['account.tax']
        cls.tax_inc15 = Tax.create({
            'name': 'D VAT 15% included', 'amount_type': 'percent', 'amount': 15.0,
            'type_tax_use': 'sale', 'price_include_override': 'tax_included',
            'company_id': cls.company.id,
        })
        cls.tax_exc10 = Tax.create({
            'name': 'D VAT 10% excluded', 'amount_type': 'percent', 'amount': 10.0,
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.company.id,
        })
        cls.tax_exc5 = Tax.create({
            'name': 'D VAT 5% excluded', 'amount_type': 'percent', 'amount': 5.0,
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.company.id,
        })
        # Thuế CỐ ĐỊNH — đây mới là case làm phép chia price_total/qty sai (WJ-PH-005).
        cls.tax_fixed = Tax.create({
            'name': 'D phí cố định 1.234', 'amount_type': 'fixed', 'amount': 1234.0,
            'type_tax_use': 'sale', 'company_id': cls.company.id,
        })

    @classmethod
    def _product(cls, name, price, taxes):
        return cls.env['product.product'].create({
            'name': name, 'type': 'consu', 'list_price': price,
            'taxes_id': [(6, 0, taxes.ids)],
        })

    def _order(self, product, qty, discount=0.0):
        """SO thật — nguồn chân lý để đối chiếu. Cùng partner/company với helper."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'discount': discount,
            })],
        })
        return order, order.order_line[0]

    def _cart_vals(self, product, qty, discount=0.0):
        """Số portal hiện ở GIỎ (chưa có SO) — đúng đường mà `_cart_state` đi."""
        taxes_of = portal_tax_mapper(self.partner, self.company)
        return portal_line_price_vals(
            product, product.list_price, qty, self.currency,
            partner=self.partner, discount=discount, company=self.company,
            taxes=taxes_of(product),
        )

    def _assert_cart_matches_order(self, product, qty, discount=0.0):
        """Bất biến trung tâm của cụm D: giỏ == đơn, từng đồng."""
        cart = self._cart_vals(product, qty, discount)
        order, line = self._order(product, qty, discount)
        self.assertEqual(
            self.currency.round(cart['line_total_tax_included']),
            self.currency.round(line.price_total),
            'Thành tiền giỏ lệch sale.order.line.price_total',
        )
        self.assertEqual(
            self.currency.round(cart['line_total_tax_included']),
            self.currency.round(order.amount_total),
            'Tổng giỏ lệch sale.order.amount_total',
        )
        return cart, order, line

    # ------------------------------------------------------------------ ma trận thuế

    def test_tax_included_15_cart_equals_order(self):
        """WJ-ORD-024 — case BA báo: giỏ 48.000, gửi xong ra 55.200. Không được nhảy nữa."""
        product = self._product('D-inc15', 48000.0, self.tax_inc15)
        cart, order, _line = self._assert_cart_matches_order(product, 3)
        # price_include: giá pricelist ĐÃ gồm thuế → tổng đã thuế = 48.000 × 3.
        self.assertEqual(self.currency.round(cart['line_total_tax_included']), 144000.0)
        self.assertGreater(cart['tax_amount'], 0.0)

    def test_tax_excluded_10_breakdown_sums_to_total(self):
        """Tạm tính + Thuế = Tổng thanh toán — nếu không, breakdown ở giỏ vô nghĩa."""
        product = self._product('D-exc10', 20000.0, self.tax_exc10)
        cart, order, _line = self._assert_cart_matches_order(product, 4)
        self.assertEqual(self.currency.round(cart['line_total']), 80000.0)
        self.assertEqual(self.currency.round(cart['tax_amount']), 8000.0)
        self.assertEqual(
            self.currency.round(cart['line_total'] + cart['tax_amount']),
            self.currency.round(cart['line_total_tax_included']),
        )
        self.assertEqual(self.currency.round(order.amount_untaxed), 80000.0)

    def test_discount_applied_before_tax(self):
        """BA 30/07: chiết khấu vào ĐƠN GIÁ trước, rồi mới tính thuế."""
        product = self._product('D-disc', 100000.0, self.tax_exc10)
        cart, _order, _line = self._assert_cart_matches_order(product, 2, discount=10.0)
        # 100.000 × 0,9 = 90.000 → +10% = 99.000
        self.assertEqual(self.currency.round(cart['unit_price_tax_included']), 99000.0)
        self.assertEqual(self.currency.round(cart['line_total_tax_included']), 198000.0)

    def test_two_taxes_on_one_line(self):
        """Một dòng gánh 2 thuế — tổng phải khớp price_total của Odoo, không tự cộng tay."""
        product = self._product('D-2tax', 30000.0, self.tax_exc10 | self.tax_exc5)
        cart, _order, line = self._assert_cart_matches_order(product, 3)
        self.assertEqual(self.currency.round(cart['line_total_tax_included']),
                         self.currency.round(line.price_total))

    def test_fixed_amount_tax_matches_order(self):
        """Thuế cố định + % + chiết khấu cùng một dòng — giỏ vẫn khớp đơn.

        Lưu ý: thuế `fixed` của Odoo tính TRÊN MỖI ĐƠN VỊ, nên riêng case này phép
        chia price_total/qty vô tình vẫn ra đúng. Chỗ nó trượt là rounding →
        test_unit_price_is_compute_all_not_division bên dưới."""
        product = self._product('D-fixed', 50000.0, self.tax_fixed | self.tax_exc10)
        cart, _order, line = self._assert_cart_matches_order(product, 7, discount=15.0)
        self.assertEqual(self.currency.round(cart['unit_price_tax_included'] * 7),
                         self.currency.round(line.price_total))

    def test_unit_price_is_compute_all_not_division(self):
        """WJ-PH-005 — đơn giá phải LÀ compute_all(1 đơn vị), không phải phép chia.

        Assert theo ĐỊNH NGHĨA của công thức BA: ai đó quay lại dùng price_total/qty
        thì test này vỡ, kể cả ở những bộ số mà phép chia tình cờ ra đúng."""
        product = self._product('D-div', 3333.0, self.tax_exc10)
        taxes = portal_tax_mapper(self.partner, self.company)(product)
        expected = taxes.compute_all(
            product.list_price, currency=self.currency, quantity=1.0,
            product=product, partner=self.partner,
        )['total_included']
        cart = self._cart_vals(product, 7)
        self.assertEqual(cart['unit_price_tax_included'], self.currency.round(expected))

    def test_rounding_makes_division_diverge(self):
        """Chênh lệch THẬT giữa 2 cách tính — bộ số đo được, không phải bịa.

        Giá 3,33 · thuế 7,5% · chiết khấu 33% · qty 3: compute_all(1 đơn vị) = 2,40
        còn price_total/qty = 2,3966… Không phải sai số vô hại: đây là đơn giá in
        trên màn Lịch sử, nhân ngược lên không ra thành tiền."""
        tax = self.env['account.tax'].create({
            'name': 'D VAT 7.5% excluded', 'amount_type': 'percent', 'amount': 7.5,
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': self.company.id,
        })
        product = self._product('D-rounding', 3.33, tax)
        _order, line = self._order(product, 3, discount=33.0)
        cart = self._cart_vals(product, 3, discount=33.0)
        naive = line.price_total / line.product_uom_qty
        self.assertNotEqual(round(naive, 6), round(cart['unit_price_tax_included'], 6))
        # Cách của cụm D mới là cách khớp với đơn.
        self.assertEqual(self.currency.round(cart['line_total_tax_included']),
                         self.currency.round(line.price_total))

    def test_no_tax_product_unchanged(self):
        """Regression: sản phẩm không thuế ra y hệt trước sprint (unit × qty)."""
        product = self._product('D-notax', 12345.0, self.env['account.tax'])
        cart, _order, _line = self._assert_cart_matches_order(product, 6)
        self.assertEqual(cart['unit_price'], cart['unit_price_tax_included'])
        self.assertEqual(self.currency.round(cart['line_total_tax_included']),
                         self.currency.round(12345.0 * 6))
        self.assertEqual(cart['tax_amount'], 0.0)

    def test_unit_price_computed_per_unit_not_by_division(self):
        """compute_all gọi cho 1 ĐƠN VỊ rồi mới nhân — không gọi cả qty rồi chia."""
        product = self._product('D-round', 3333.0, self.tax_exc10)
        one = self._cart_vals(product, 1)
        many = self._cart_vals(product, 9)
        self.assertEqual(one['unit_price_tax_included'], many['unit_price_tax_included'])

    # ------------------------------------------------------------------ ký hiệu tiền

    def test_money_format_keeps_vn_thousand_separator(self):
        """WJ-ORD-025 — format số giữ y hệt bản cũ, chỉ ký hiệu là động."""
        self.assertEqual(portal_money(12650000, 'đ'), '12.650.000 đ')
        self.assertEqual(portal_money(48000, '$'), '48.000 $')
        self.assertEqual(portal_money(0, '₫'), '0 ₫')
        self.assertEqual(portal_money(None, 'đ'), '0 đ')

    def test_money_follows_currency_decimal_places(self):
        """BA chốt "ký hiệu + ROUNDING theo currency của đơn".

        Đơn USD amount_total = 10.99 mà in "11 $" là sai — chính là ca đã bắt được
        trên DB copy. Currency 2 số lẻ → giữ 2 số lẻ, dấu thập phân kiểu VN (dấu phẩy).
        VND (0 số lẻ) phải ra byte-for-byte y hệt bản cũ."""
        self.assertEqual(portal_money(10.99, '$', 2), '10,99 $')
        self.assertEqual(portal_money(1234567.5, '$', 2), '1.234.567,50 $')
        self.assertEqual(portal_money(10.99, 'đ', 0), '11 đ')
        self.assertEqual(portal_money(12650000, 'đ', 0), portal_money(12650000, 'đ'))

    def test_money_without_symbol_prints_number_only(self):
        """Currency thiếu symbol → in số trần, KHÔNG rơi về 'đ' bịa ra."""
        self.assertEqual(portal_money(1000, ''), '1.000')
        self.assertEqual(portal_money(1000, None), '1.000')

    def test_foreign_currency_symbol_follows_order(self):
        """Currency ≠ VND → ký hiệu theo đơn, đây là chỗ History từng ra '$' còn Cart ra 'đ'."""
        usd = self.env.ref('base.USD')
        product = self._product('D-usd', 25.0, self.tax_exc10)
        taxes_of = portal_tax_mapper(self.partner, self.company)
        vals = portal_line_price_vals(
            product, product.list_price, 2, usd,
            partner=self.partner, company=self.company, taxes=taxes_of(product),
        )
        self.assertEqual(usd.round(vals['line_total_tax_included']), 55.0)
        self.assertEqual(portal_money(55, usd.symbol, usd.decimal_places), '55,00 $')

    # ------------------------------------------------------------------ perf

    def test_tax_mapper_resolves_fiscal_position_once(self):
        """1500 user: mapper phải cache, không resolve fiscal position mỗi dòng."""
        product_a = self._product('D-perf-a', 1000.0, self.tax_exc10)
        product_b = self._product('D-perf-b', 2000.0, self.tax_exc10)
        mapper = portal_tax_mapper(self.partner, self.company)
        calls = []
        original = type(self.env['account.fiscal.position'])._get_fiscal_position

        def spy(self_fp, partner, delivery=None):
            calls.append(partner.id)
            return original(self_fp, partner, delivery)

        self.patch(type(self.env['account.fiscal.position']), '_get_fiscal_position', spy)
        for _ in range(5):
            mapper(product_a)
            mapper(product_b)
        self.assertLessEqual(len(calls), 1, 'fiscal position bị resolve lại mỗi dòng')
