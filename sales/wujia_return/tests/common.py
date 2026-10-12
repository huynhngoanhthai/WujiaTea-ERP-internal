"""Dữ liệu dùng chung cho test đổi trả / bù hàng (model + portal)."""
import io
from datetime import timedelta

from werkzeug.datastructures import FileStorage

from odoo import fields

from odoo.addons.wujia_return.models.wujia_return_request import ORDER_WINDOW_DAYS


def load_vi(env, modules=('wujia_return',)):
    """Bật vi_VN + nạp .po của `modules`; trả env `lang=vi_VN`.

    J-V6: câu gốc của module là tiếng Anh ⇒ test assert câu tiếng Việt chạy ở vi_VN, không xoá assert
    (Phần V §6 #5). `_activate_lang` không nạp .po ⇒ `_update_translations`.
    """
    env['res.lang']._activate_lang('vi_VN')
    env['ir.module.module'].search([
        ('name', 'in', modules), ('state', '=', 'installed'),
    ])._update_translations(['vi_VN'])
    return env(context=dict(env.context, lang='vi_VN'))


JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 60
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 60
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 60
MOV = b'\x00\x00\x00\x14ftypqt  ' + b'\x00' * 60
TEXT = b'just a plain text file, definitely not an image'


def _file(data, filename='a.jpg', content_type='image/jpeg', pad=0):
    return FileStorage(stream=io.BytesIO(data + b'\x00' * pad),
                       filename=filename, content_type=content_type)


class ReturnFixture:
    """1 cửa hàng + 1 cửa hàng khác, sản phẩm có/không cấu hình bù, đơn giao xong trong/ngoài 10 ngày và chưa giao."""

    @classmethod
    def _setup_return_data(cls):
        env = cls.env
        Partner = env['res.partner']
        Franchise = env['wujia.franchise.management']
        cls.franchise = Franchise.create({
            'code': 'CT3A', 'name': 'CT3 store A', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'CT3A partner'}).id})
        cls.other = Franchise.create({
            'code': 'CT3B', 'name': 'CT3 store B', 'franchise_end_date': '2030-01-01',
            'partner_id': Partner.create({'name': 'CT3B partner'}).id})

        cls.uom_kg = env.ref('uom.product_uom_kgm')
        cls.uom_unit = env.ref('uom.product_uom_unit')
        cls.tax = env['account.tax'].create({
            'name': 'CT3 VAT 8', 'amount': 8.0, 'amount_type': 'percent',
            'type_tax_use': 'sale'})
        cls.product = env['product.product'].create({
            'name': 'CT3 tea', 'type': 'consu', 'list_price': 100_000,
            'uom_id': cls.uom_kg.id, 'taxes_id': [(6, 0, cls.tax.ids)],
            'compensation_enabled': True,
            'compensation_policy': 'accumulate',
            'compensation_claim_uom_id': cls.uom_kg.id,
            'compensation_delivery_uom_id': cls.uom_kg.id,
            'compensation_unit_qty': 10.0,
        })
        cls.product_noconf = env['product.product'].create({
            'name': 'CT3 unconfigured', 'type': 'consu', 'list_price': 50_000})

        cls.issue_type = env['wujia.return.issue.type'].create({
            'name': 'CT3 broken', 'active': True})

        cls.order_ok = cls._order(cls.franchise, cls.product, confirm=True)
        cls._deliver(cls.order_ok, days_ago=2)
        cls.order_draft = cls._order(cls.franchise, cls.product, confirm=False)
        cls.order_old = cls._order(cls.franchise, cls.product, confirm=True)
        cls.order_old.date_order = fields.Datetime.now() - timedelta(days=ORDER_WINDOW_DAYS * 2)
        cls._deliver(cls.order_old, days_ago=3)
        cls.order_undelivered = cls._order(cls.franchise, cls.product, confirm=True)
        cls.order_expired = cls._order(cls.franchise, cls.product, confirm=True)
        cls._deliver(cls.order_expired, days_ago=ORDER_WINDOW_DAYS + 1)
        cls.order_other = cls._order(cls.other, cls.product, confirm=True)
        cls._deliver(cls.order_other, days_ago=1)

    @classmethod
    def _order(cls, franchise, product, confirm=False):
        order = cls.env['sale.order'].create({
            'partner_id': franchise.partner_id.id,
            'franchise_id': franchise.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 5})],
        })
        if confirm:
            order.action_confirm()
        return order

    @classmethod
    def _deliver(cls, order, days_ago=0, qty=None, picking=None):
        """Validate một phiếu xuất (``qty`` < SL đặt ⇒ Odoo tạo backorder) rồi lùi ``date_done``."""
        picking = picking or order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and p.state not in ('done', 'cancel'))[:1]
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty if qty is None else qty
            move.picked = True
        picking._action_done()
        picking.date_done = fields.Datetime.now() - timedelta(days=days_ago)
        return picking

    @classmethod
    def _request(cls, franchise=None, order=None, state='submitted', **kw):
        franchise = franchise or cls.franchise
        order = order or cls.order_ok
        vals = {
            'franchise_id': franchise.id,
            'sale_order_id': order.id,
            'sale_order_line_id': order.order_line[0].id,
            'request_uom_id': cls.uom_kg.id,
            'request_qty': 12.0,
            'opening_datetime': fields.Datetime.now(),
            'issue_type_id': cls.issue_type.id,
            'state': state,
        }
        vals.update(kw)
        return cls.env['wujia.return.request'].create(vals)
