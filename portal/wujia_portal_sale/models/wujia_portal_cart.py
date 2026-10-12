import logging
from datetime import timedelta

import psycopg2
from psycopg2 import errors as pg_errors

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import plaintext2html

from odoo.addons.wujia_order_window.models.sale_order import OrderWindowClosed

_logger = logging.getLogger(__name__)

INT_MAX = 2147483647
# WJ-ORD-028: cửa sổ coi một lần gửi lặp (double-click lọt, Back rồi gửi lại) là CÙNG một lần gửi.
RESUBMIT_WINDOW = timedelta(minutes=2)


class PortalOrderError(UserError):
    """Lỗi nghiệp vụ gửi đơn portal — controller map `code` sang redirect."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class WujiaPortalCart(models.Model):
    """Giỏ hàng portal DÙNG CHUNG theo cửa hàng (BA FINAL: 1 store = 1 giỏ active,
    mọi user có membership đều thao tác cùng giỏ, last-write-wins).
    Cart persistent — sau submit chỉ clear line + note, không xoá record.
    Truy cập từ portal luôn qua controller (sudo + gate franchise), không có ACL trực tiếp.
    """
    _name = 'wujia.portal.cart'
    _description = 'Wujia Portal Cart (shared per store)'

    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        required=True,
        ondelete='cascade',
        index=True,
    )
    note = fields.Text(string='Order note')
    line_ids = fields.One2many('wujia.portal.cart.line', 'cart_id')

    _franchise_uniq = models.Constraint(
        'UNIQUE (franchise_id)',
        'Each store can only have one cart.',
    )

    @api.depends('franchise_id')
    def _compute_display_name(self):
        for cart in self:
            cart.display_name = cart.env._(
                'Cart [%(code)s] %(name)s',
                code=cart.franchise_id.code or '?', name=cart.franchise_id.name or '',
            )

    @api.model
    def _get_for_store(self, fid, create=False):
        """Giỏ chung của store — KHÔNG filter theo user (BA row 5).

        Race 2 request cùng tạo giỏ đầu tiên: unique(franchise_id) →
        IntegrityError bọc savepoint (không savepoint = abort cả transaction),
        thua thì search lại lấy giỏ của request thắng.
        """
        cart = self.search([('franchise_id', '=', fid)], limit=1)
        if cart or not create:
            return cart
        try:
            with self.env.cr.savepoint():
                cart = self.create({'franchise_id': fid})
        except psycopg2.IntegrityError:
            cart = self.search([('franchise_id', '=', fid)], limit=1)
        return cart

    def _lock_lines(self):
        """Khoá giỏ NOWAIT + snapshot dòng tại lúc khoá (BA: last-write-wins).

        Savepoint BẮT BUỘC: LockNotAvailable nằm trong danh sách Odoo tự retry
        request; bọc savepoint thì dừng ở đây thay vì retry 5 lần. Row lock sống
        tới hết transaction (RELEASE SAVEPOINT không nhả lock)."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM wujia_portal_cart WHERE id = %s FOR UPDATE NOWAIT",
                    (self.id,),
                )
                self.env['wujia.portal.cart.line'].invalidate_model()
                self.invalidate_recordset()
                return self.line_ids
        except pg_errors.LockNotAvailable:
            raise PortalOrderError('CART_IS_PROCESSING')

    @api.model
    def _portal_just_submitted_order(self, franchise_id, user_id):
        """Đơn portal mà CHÍNH user này vừa gửi cho cửa hàng này (≤ RESUBMIT_WINDOW), còn chờ xác nhận.

        WJ-ORD-028: lần gửi thứ hai lọt qua lớp giao diện (double-click, Back rồi gửi lại) gặp giỏ
        đã trống ⇒ `CART_EMPTY`. Khoá giỏ NOWAIT đã bảo đảm chỉ ra MỘT đơn; hàm này chỉ để controller
        dẫn người dùng tới đơn vừa tạo thay vì báo "giỏ trống" gây hiểu là chưa gửi được."""
        return self.env['sale.order'].search([
            ('franchise_id', '=', franchise_id),
            ('is_portal_order', '=', True),
            ('portal_requester_user_id', '=', user_id),
            ('state', 'in', ('draft', 'sent')),
            ('create_date', '>=', fields.Datetime.now() - RESUBMIT_WINDOW),
        ], order='id desc', limit=1)

    def action_submit_order(self, note=None):
        """Giỏ → SO draft portal (BA: không action_confirm). Raise PortalOrderError(code).

        POR-022 "1 store 1 báo giá portal": huỷ draft/sent portal cũ bằng write state
        (không action_cancel — tránh cascade huỷ invoice + chatter storm). Tạo SO,
        huỷ cũ, xoá giỏ trong MỘT savepoint: lỗi ở bước nào cũng không để lại SO mới."""
        self.ensure_one()
        franchise = self.franchise_id
        if franchise.portal_locked:
            raise PortalOrderError('branch_locked')
        if not self.line_ids:
            raise PortalOrderError('CART_EMPTY')
        lines = self._lock_lines()
        if not lines:
            raise PortalOrderError('CART_EMPTY')

        allowed, window = self.env['res.config.settings']._is_within_order_window(franchise=franchise)
        if window.get('tz_missing'):
            raise PortalOrderError('STORE_TZ_NOT_CONFIGURED')
        if not allowed:
            raise PortalOrderError('ORDER_TIME_CLOSED')

        reasons = {line._portal_invalid_reason() for line in lines} - {None}
        if reasons:
            raise PortalOrderError('CART_QUANTITY_INVALID' if reasons == {'CART_QUANTITY_INVALID'}
                                   else 'CART_HAS_INVALID_PRODUCT')

        partner = franchise.partner_id
        if not partner:
            raise PortalOrderError('STORE_CUSTOMER_NOT_CONFIGURED')

        SO = self.env['sale.order']
        old_quotations = SO.search([
            ('franchise_id', '=', franchise.id),
            ('is_portal_order', '=', True),
            ('state', 'in', ('draft', 'sent')),
        ])
        if any(old_quotations.mapped('locked')):
            _logger.warning('Portal submit blocked: locked portal quotation(s) %s (store %s)',
                            old_quotations.filtered('locked').ids, franchise.id)
            raise PortalOrderError('OLD_PORTAL_QUOTATION_CANCEL_FAILED')

        member = self.env['wujia.franchise.member'].find_active_membership(
            self.env.uid, franchise.id)
        note_text = (note or self.note or '').strip()[:1000]
        so_vals = {
            'is_portal_order': True,
            'franchise_id': franchise.id,
            'franchise_partner_id': partner.id,
            'partner_id': partner.id,
            # Pricelist tường minh = pricelist đã dùng tính giá catalog/giỏ.
            'pricelist_id': partner.property_product_pricelist.id or False,
            # sudo() giữ env.uid → create_uid = user portal (POR-019).
            'portal_requester_user_id': self.env.uid,
            'portal_member_id': member.id if member else False,
            'origin': 'Wujia Portal',
            # note là Html: plaintext2html escape input user + giữ xuống dòng.
            'portal_note': note_text or False,
            'note': plaintext2html(note_text) if note_text else False,
            'order_line': [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.qty,
                    'product_uom_id': line.product_id.uom_id.id,
                }) for line in lines
            ],
        }
        stage = 'create'
        try:
            with self.env.cr.savepoint():
                order = SO.create(so_vals)
                stage = 'cancel'
                old_quotations.write({'state': 'cancel'})
                still_open = old_quotations.filtered(lambda o: o.state != 'cancel')
                if still_open:
                    raise UserError(f'cancel failed: {still_open.ids}')
                lines.unlink()
                self.write({'note': False})
        except Exception as e:
            if stage == 'cancel':
                _logger.exception('Portal submit: cancel-old/clear-cart failed (store %s)', franchise.id)
                raise PortalOrderError('OLD_PORTAL_QUOTATION_CANCEL_FAILED') from e
            if isinstance(e, ValidationError):
                _logger.warning('Portal order create rejected (store %s): %s', franchise.id, e)
                if isinstance(e, OrderWindowClosed):
                    raise PortalOrderError('ORDER_TIME_CLOSED') from e
            else:
                _logger.exception('Portal order create failed (store %s)', franchise.id)
            raise PortalOrderError('ORDER_CREATE_FAILED') from e
        return order


class WujiaPortalCartLine(models.Model):
    """1 sản phẩm = 1 dòng/giỏ (unique cart+product — điều kiện cho SQL upsert
    ON CONFLICT ở `_portal_add`). Không lưu giá: giá luôn tính lại từ pricelist."""
    _name = 'wujia.portal.cart.line'
    _description = 'Wujia Portal Cart Line'

    cart_id = fields.Many2one(
        'wujia.portal.cart',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        required=True,
        ondelete='cascade',
    )
    qty = fields.Integer(default=0)

    _cart_product_uniq = models.Constraint(
        'UNIQUE (cart_id, product_id)',
        'Each product can only have one line in the cart.',
    )

    @api.model
    def _portal_add(self, cart, product, increment):
        """Upsert nguyên tử (giỏ chung, nhiều thiết bị cùng thêm) → (line_id, qty mới).

        LEAST chặn trần max_qty ngay trong SQL; cột audit set tay vì raw INSERT."""
        cap = product.max_qty if product.max_qty > 0 else INT_MAX
        self.env.cr.execute(
            """
            INSERT INTO wujia_portal_cart_line
                   (cart_id, product_id, qty, create_uid, create_date, write_uid, write_date)
            VALUES (%(cart)s, %(product)s, LEAST(%(inc)s, %(cap)s),
                    %(uid)s, now() AT TIME ZONE 'UTC', %(uid)s, now() AT TIME ZONE 'UTC')
            ON CONFLICT (cart_id, product_id) DO UPDATE
               SET qty = LEAST(wujia_portal_cart_line.qty + %(inc)s, %(cap)s),
                   write_uid = %(uid)s,
                   write_date = now() AT TIME ZONE 'UTC'
            RETURNING id, qty
            """,
            {'cart': cart.id, 'product': product.id, 'inc': increment,
             'cap': cap, 'uid': self.env.uid},
        )
        line_id, new_qty = self.env.cr.fetchone()
        self.invalidate_model()
        cart.invalidate_recordset()
        return line_id, new_qty

    def _portal_step(self, sign):
        """±1 bước (= min_qty) NGUYÊN TỬ (WJ-ORD-002) → (qty mới, đã xoá dòng?).

        UPDATE khoá dòng tới hết transaction ⇒ 2 request gần đồng thời áp tuần tự,
        unlink khi rơi dưới min an toàn với request song song."""
        self.ensure_one()
        product = self.product_id
        step = product.min_qty
        cap = product.max_qty if product.max_qty > 0 else INT_MAX
        self.env.cr.execute(
            """
            UPDATE wujia_portal_cart_line
               SET qty = LEAST(qty + %(delta)s, %(cap)s),
                   write_uid = %(uid)s,
                   write_date = now() AT TIME ZONE 'UTC'
             WHERE id = %(line)s
            RETURNING qty
            """,
            {'delta': sign * step, 'cap': cap, 'line': self.id, 'uid': self.env.uid},
        )
        row = self.env.cr.fetchone()
        cart = self.cart_id
        self.invalidate_model()
        cart.invalidate_recordset()
        new_qty = row[0] if row else 0
        if new_qty < step:
            self.unlink()
            cart.invalidate_recordset()
            return new_qty, True
        return new_qty, False

    def _portal_invalid_reason(self):
        """Mã lỗi hiển thị per-line trên giỏ (BA row 11) — None khi dòng đặt được."""
        self.ensure_one()
        product = self.product_id
        if not product._portal_is_orderable():
            return 'PRODUCT_NOT_AVAILABLE'
        error = product._portal_qty_error(self.qty)
        if not error:
            return None
        return 'MIN_QTY_NOT_CONFIGURED' if error[0] == 'MIN_QTY_NOT_CONFIGURED' else 'CART_QUANTITY_INVALID'
