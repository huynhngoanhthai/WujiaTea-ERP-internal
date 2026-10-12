"""UAT-BH-001 — wizard "Xử lý bù hàng" phải tạo được SO bù qua ĐÚNG đường web client.

Chạy: `--test-tags wujia_return_d1`.

Test cũ (`test_return_controller.py`) gọi `create({})` thuần ORM nên giữ nguyên mọi
giá trị `default_get` ⇒ không bao giờ lộ lỗi thật: web client **bỏ** field readonly
không có `force_save` khi gửi vals (`web/.../relational_model/record.js` _getChanges,
và `views/fields/field.js` lấy luôn readonly của field Python khi arch không ghi).
Ở đây mô phỏng client theo hướng KHẮT KHE NHẤT (chỉ giữ field của sub-view list, bỏ
hẳn `line_ids`) — server phải tự tính lại được từ `request_ids`.
"""

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import ReturnFixture

WIZARD = 'wujia.compensation.process.wizard'
VIEW = 'wujia_return.view_compensation_process_wizard_form'


def _sent_by_client(node, vals):
    """Lọc vals theo đúng luật client: bỏ field readonly không có force_save.

    `node` = thẻ cha (form hoặc list) chứa các `<field>`. Field không có mặt trong
    arch cũng bị bỏ — client chỉ gửi activeFields của sub-view đang render.
    """
    keep = {}
    for f in node.findall('./field'):
        name = f.get('name')
        readonly = f.get('readonly') in ('1', 'True')
        if readonly and f.get('force_save') not in ('1', 'True'):
            continue
        keep[name] = f
    return {k: v for k, v in vals.items() if k in keep}, keep


@tagged('post_install', '-at_install', 'wujia_return_d1')
class TestCompensationWizardClientPath(TransactionCase, ReturnFixture):
    """SO bù phải được tạo dù client chỉ gửi lại đúng phần không readonly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_return_data()
        # Ca BA nêu #2: đơn vị bù KHÁC đơn vị đặt hàng (quyền lợi kg → giao theo thùng).
        cls.product_box = cls.env['product.product'].create({
            'name': 'CT3 tea box', 'type': 'consu', 'list_price': 90_000,
            'uom_id': cls.uom_kg.id,
            'compensation_enabled': True,
            'compensation_policy': 'accumulate',
            'compensation_claim_uom_id': cls.uom_kg.id,
            'compensation_delivery_uom_id': cls.uom_unit.id,
            'compensation_unit_qty': 10.0,
        })

    # ------------------------------------------------------------------ helpers
    def _approved(self, qty=20.0, product=None, delivery_uom=None):
        rr = self._request(
            state='approved', resolution_type='compensation',
            approved_qty=qty, approved_uom_id=self.uom_kg.id,
            compensation_product_id=(product or self.product).id,
            compensation_delivery_uom_id=(delivery_uom or self.uom_kg).id,
            compensation_unit_qty=10.0, compensation_policy='accumulate')
        rr.approved_date = fields.Datetime.now()
        return rr

    def _arch(self):
        view = self.env.ref(VIEW)
        return etree.fromstring(
            self.env[WIZARD].get_view(view.id, 'form')['arch'])

    def _create_like_client(self, requests):
        """default_get → lọc y như client → create. Trả wizard đã lưu."""
        Wizard = self.env[WIZARD].with_context(active_ids=requests.ids)
        defaults = Wizard.default_get(list(Wizard._fields))
        arch = self._arch()
        root_vals, root_fields = _sent_by_client(arch, defaults)

        group_node = root_fields.get('group_ids')
        list_node = group_node.find('./list')
        cmds = []
        for cmd in root_vals.get('group_ids', []):
            gvals = dict(cmd[2])
            gvals.pop('line_ids', None)   # không nằm trong sub-view list ⇒ client không gửi
            gvals, _ = _sent_by_client(list_node, gvals)
            cmds.append((0, 0, gvals))
        root_vals['group_ids'] = cmds
        return Wizard.create(root_vals)

    # -------------------------------------------------------------------- tests
    def test_view_keeps_force_save_on_every_readonly_field(self):
        """Bất biến chống tái phát: readonly trong wizard PHẢI kèm force_save."""
        missing = [
            f.get('name')
            for f in self._arch().iter('field')
            if f.get('readonly') in ('1', 'True')
            and f.get('force_save') not in ('1', 'True')
        ]
        self.assertEqual(missing, [], "field readonly thiếu force_save → client sẽ bỏ")

    def test_same_uom_creates_zero_priced_so(self):
        """Ca BA #1 — RTN/26/00001: đơn vị bù giống đơn vị đặt hàng."""
        rr = self._approved()
        wizard = self._create_like_client(rr)
        wizard.action_confirm()

        allocation = rr.allocation_ids
        self.assertEqual(len(allocation), 1)
        order = allocation.sale_order_id
        self.assertTrue(order.is_return_order)
        self.assertEqual(order.state, 'sent')
        self.assertEqual(order.amount_untaxed, 0.0)
        self.assertEqual(order.order_line.product_uom_qty, 2.0)   # 20kg / 10kg mỗi đơn vị
        self.assertEqual(allocation.allocated_qty, 20.0)
        self.assertEqual(rr.state, 'processing')

    def test_other_uom_creates_so_in_delivery_uom(self):
        """Ca BA #2 — RTN/26/00002: quyền lợi kg, giao theo thùng."""
        rr = self._approved(qty=25.0, product=self.product_box,
                            delivery_uom=self.uom_unit)
        wizard = self._create_like_client(rr)
        wizard.action_confirm()

        line = rr.allocation_ids.sale_order_line_id
        self.assertEqual(line.product_id, self.product_box)
        self.assertEqual(line.product_uom_id, self.uom_unit)
        self.assertEqual(line.product_uom_qty, 2.0)               # floor(25/10)
        self.assertEqual(line.price_unit, 0.0)
        self.assertEqual(rr.allocation_ids.allocated_qty, 20.0)   # phần lẻ 5kg còn treo
        self.assertEqual(rr.unallocated_qty, 5.0)

    def test_two_requests_same_store_share_one_order(self):
        """1 SO / 1 cửa hàng / 1 lần xử lý, FIFO theo ngày duyệt."""
        first = self._approved(qty=20.0)
        second = self._approved(qty=10.0)
        second.approved_date = fields.Datetime.now()
        requests = first | second

        wizard = self._create_like_client(requests)
        wizard.action_confirm()

        orders = requests.allocation_ids.sale_order_id
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.order_line.product_uom_qty, 3.0)  # 30kg / 10
        self.assertEqual(first.allocation_ids.allocated_qty, 20.0)
        self.assertEqual(second.allocation_ids.allocated_qty, 10.0)

    def test_reprocess_does_not_create_duplicate_order(self):
        """Thao tác lại không tạo SO trùng — yêu cầu đã hết quyền lợi thì mở không được."""
        rr = self._approved()
        self._create_like_client(rr).action_confirm()
        order_count = len(rr.allocation_ids.sale_order_id)

        with self.assertRaises(UserError):
            self._create_like_client(rr)
        self.assertEqual(len(rr.allocation_ids.sale_order_id), order_count)

    def test_stale_wizard_is_rejected(self):
        """Quyền lợi đổi sau khi mở wizard ⇒ chặn, không tạo SO sai số."""
        rr = self._approved()
        wizard = self._create_like_client(rr)
        rr.write({'state': 'cancelled'})

        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertFalse(rr.allocation_ids)
