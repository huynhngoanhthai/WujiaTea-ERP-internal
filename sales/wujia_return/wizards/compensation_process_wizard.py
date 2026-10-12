import math

from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

UOM_DIGITS = 'Product Unit of Measure'
EPS = 1e-6


class CompensationProcessWizard(models.TransientModel):
    """Wizard "Xử lý bù hàng" — gom yêu cầu đã duyệt → SO 0đ + phân bổ FIFO (BA K2).

    default_get chạy bước 1–5 (validate/group/FIFO/tính SL đề xuất); HQ chỉnh
    delivery_qty (bước 6); action_confirm chạy bước 7–8 (lock re-validate + tạo
    SO + allocation). 1 SO / 1 cửa hàng / 1 lần xử lý (BA chốt điểm 5).
    """

    _name = 'wujia.compensation.process.wizard'
    _description = 'Process compensation'

    request_ids = fields.Many2many('wujia.return.request', string='Compensation request')
    group_ids = fields.One2many(
        'wujia.compensation.process.wizard.group', 'wizard_id',
        string='Compensation SO group',
    )
    skipped_count = fields.Integer(string='Skipped requests', readonly=True)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _uom_root(uom):
        """Gốc cây đơn vị (Odoo 19 bỏ category_id, dùng cây relative_uom_id)."""
        while uom.relative_uom_id:
            uom = uom.relative_uom_id
        return uom

    @staticmethod
    def _convert(qty, from_uom, to_uom, rounding_method='UP'):
        """Quy đổi qua engine UoM Odoo. Khác NHÓM đơn vị → raise (misconfig BA).

        ⚠️ Odoo 19 `_compute_quantity` KHÔNG tự kiểm nhóm (chỉ nhân factor) → tự
        guard bằng gốc cây, nếu không quy đổi khác nhóm (kg ↔ cái) ra số vô nghĩa.
        """
        if not from_uom or not to_uom or from_uom == to_uom:
            return qty
        _root = CompensationProcessWizard._uom_root
        if _root(from_uom) != _root(to_uom):
            raise UserError(_(
                "Cannot convert '%s' ↔ '%s' (different UoM categories).",
                from_uom.display_name, to_uom.display_name))
        return from_uom._compute_quantity(qty, to_uom, rounding_method=rounding_method)

    @staticmethod
    def _claim_to_delivery(claim_qty, policy, unit_qty, claim_uom, delivery_uom):
        """Quyền lợi → SL giao. Trả (delivery_qty, covered_claim).

        exact: làm tròn XUỐNG (không bù vượt quyền lợi); covered = phần SL giao
        quy ngược lại quyền lợi (tránh double-UP đẩy covered > total_claim).
        """
        if policy == 'accumulate':
            if unit_qty <= 0:
                return 0.0, 0.0
            claim_qty = float_round(claim_qty, precision_rounding=(claim_uom.rounding or 0.01))
            units = math.floor((claim_qty + EPS) / unit_qty)
            return float(units), units * unit_qty
        deliver = CompensationProcessWizard._convert(
            claim_qty, claim_uom, delivery_uom, 'DOWN')
        covered = CompensationProcessWizard._convert(
            deliver, delivery_uom, claim_uom, 'DOWN')
        return deliver, covered

    @staticmethod
    def _delivery_to_claim(delivery_qty, policy, unit_qty, claim_uom, delivery_uom):
        """SL giao → quyền lợi (cho delivery_qty HQ chỉnh tay). Round XUỐNG để
        covered không vượt quyền lợi khi quy đổi 2 chiều (double-UP)."""
        if policy == 'accumulate':
            return delivery_qty * unit_qty
        return CompensationProcessWizard._convert(
            delivery_qty, delivery_uom, claim_uom, 'DOWN')

    def _fifo_distribute(self, requests, covered_claim, claim_uom):
        """Rải covered_claim (ĐVT quyền lợi group) xuống requests theo FIFO.

        Trả list (request, allocate_qty) với allocate_qty theo approved_uom từng
        request (= allocation_uom_id, để rollup so trực tiếp approved_qty).
        """
        result = []
        remaining = covered_claim
        for req in requests:
            if remaining <= EPS:
                result.append((req, 0.0))
                continue
            unalloc_claim = self._convert(
                req.unallocated_qty, req.approved_uom_id, claim_uom)
            take_claim = min(remaining, unalloc_claim)
            take_approved = self._convert(take_claim, claim_uom, req.approved_uom_id)
            take_approved = min(take_approved, req.unallocated_qty)
            result.append((req, take_approved))
            remaining -= take_claim
        return result

    # --------------------------------------------------------------- build (1-5)
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        requests = self.env['wujia.return.request'].browse(active_ids).exists()
        eligible = requests.filtered(self._is_eligible)
        if not eligible:
            raise UserError(_(
                "No eligible requests to compensate.\n"
                "Only approved requests with the 'Compensation' resolution, unallocated "
                "quantity left (and a complete compensation setup) are processed."))
        res['request_ids'] = [(6, 0, eligible.ids)]
        res['group_ids'] = self._build_group_commands(eligible)
        res['skipped_count'] = len(requests) - len(eligible)
        return res

    @staticmethod
    def _is_eligible(req):
        # 'processing' được chấp nhận: yêu cầu đã tạo SO nhưng còn phần chưa phân
        # bổ (kho giao thiếu → released → unallocated_qty > 0, bù tiếp lần sau).
        if req.state not in ('approved', 'processing') \
                or req.resolution_type != 'compensation':
            return False
        if not (req.compensation_product_id and req.compensation_delivery_uom_id
                and req.approved_uom_id):
            return False
        if req.unallocated_qty <= EPS:
            return False
        if req.compensation_policy == 'accumulate' and req.compensation_unit_qty <= 0:
            return False
        return True

    def _bucket_requests(self, requests):
        """Gom request thành nhóm SO bù, FIFO theo ngày duyệt. Trả dict key → recordset.

        Dùng CHUNG cho default_get (dựng nhóm) và action_confirm (tính lại từ dữ
        liệu sống) — hai nơi phải gom y hệt nhau thì khoá nhóm mới khớp được.
        """
        ordered = requests.sorted(
            key=lambda r: (r.approved_date or r.request_date, r.request_date, r.id))
        buckets = {}
        for req in ordered:
            # approved_uom_id PHẢI trong key: allocation lưu theo approved_uom, nếu
            # 2 request khác ĐVT quyền lợi (kg/g) gộp 1 dòng SO → hook trộn sai ĐVT.
            key = (req.franchise_id.id, req.compensation_product_id.id,
                   req.approved_uom_id.id, req.compensation_delivery_uom_id.id,
                   req.compensation_policy, round(req.compensation_unit_qty, 6))
            buckets.setdefault(key, self.env['wujia.return.request'])
            buckets[key] |= req
        return buckets

    @staticmethod
    def _group_key(group):
        """Khoá của dòng nhóm trên wizard — phải khớp key của `_bucket_requests`."""
        return (group.franchise_id.id, group.compensation_product_id.id,
                group.claim_uom_id.id, group.delivery_uom_id.id,
                group.policy, round(group.unit_qty, 6))

    def _live_buckets(self):
        """Gom lại từ request_ids theo dữ liệu HIỆN TẠI (gọi sau khi đã khoá)."""
        requests = self.request_ids.exists().filtered(self._is_eligible)
        return self._bucket_requests(requests)

    def _total_claim(self, requests, claim_uom):
        """Tổng quyền lợi còn lại của nhóm, chốt về precision ĐVT quyền lợi."""
        total = sum(self._convert(r.unallocated_qty, r.approved_uom_id, claim_uom)
                    for r in requests)
        return float_round(total, precision_rounding=(claim_uom.rounding or 0.01))

    def _build_group_commands(self, requests):
        buckets = self._bucket_requests(requests)
        commands = []
        for reqs in buckets.values():
            commands.append((0, 0, self._group_vals(reqs)))
        return commands

    def _group_vals(self, reqs):
        claim_uom = reqs[0].approved_uom_id           # ĐVT quyền lợi chung group
        delivery_uom = reqs[0].compensation_delivery_uom_id
        policy = reqs[0].compensation_policy
        unit_qty = reqs[0].compensation_unit_qty
        total_claim = self._total_claim(reqs, claim_uom)
        suggested, covered = self._claim_to_delivery(
            total_claim, policy, unit_qty, claim_uom, delivery_uom)
        dist = dict(self._fifo_distribute(reqs, covered, claim_uom))
        line_cmds = [(0, 0, {
            'request_id': r.id,
            'request_uom_id': r.approved_uom_id.id,
            'request_remaining_qty': r.unallocated_qty,
            'allocate_qty': dist.get(r, 0.0),
        }) for r in reqs]
        return {
            'franchise_id': reqs[0].franchise_id.id,
            'compensation_product_id': reqs[0].compensation_product_id.id,
            'delivery_uom_id': delivery_uom.id,
            'claim_uom_id': claim_uom.id,
            'policy': policy,
            'unit_qty': unit_qty,
            'total_claim_qty': total_claim,
            'suggested_delivery_qty': suggested,
            'delivery_qty': suggested,
            'line_ids': line_cmds,
        }

    # ------------------------------------------------------------- confirm (7-8)
    def _lock_and_revalidate(self):
        """Bước 7: khoá request NOWAIT rồi gom lại nhóm theo dữ liệu SỐNG.

        Trả dict `key nhóm → recordset request`. Wizard chỉ được tin **một** con
        số do HQ nhập (`delivery_qty`); quyền lợi còn lại đọc lại từ DB dưới khoá,
        rồi so với `total_claim_qty` client gửi lên — lệch nghĩa là có người khác
        vừa đụng vào, phải mở lại wizard.
        """
        requests = self.request_ids
        if not requests:
            return {}
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM wujia_return_request WHERE id IN %s "
                    "FOR UPDATE NOWAIT",
                    (tuple(requests.ids),))
        except pg_errors.LockNotAvailable:
            raise UserError(_(
                "The request is being processed by someone else. Please try again later."))
        requests.invalidate_recordset(
            ['unallocated_qty', 'allocated_qty', 'compensated_qty', 'remaining_qty'])

        buckets = self._live_buckets()
        for g in self.group_ids:
            if not (g.franchise_id and g.compensation_product_id
                    and g.claim_uom_id and g.delivery_uom_id):
                # Bất biến kỹ thuật: view PHẢI có force_save trên field chỉ-đọc.
                raise UserError(_(
                    "The wizard lost its group data on save (missing force_save in "
                    "the view). Please report it to the technical team."))
            reqs = buckets.get(self._group_key(g))
            # Nhóm biến mất = request bị huỷ/từ chối/đã bù đủ sau khi mở wizard.
            if not reqs or abs(self._total_claim(reqs, g.claim_uom_id)
                               - (g.total_claim_qty or 0.0)) > EPS:
                raise UserError(_(
                    "Data has changed (group '%s' of store '%s'). Please close "
                    "and reopen the wizard.",
                    g.compensation_product_id.display_name or '?',
                    g.franchise_id.display_name or '?'))
        return buckets

    def action_confirm(self):
        self.ensure_one()
        if not self.group_ids or not self.request_ids:
            raise UserError(_("No groups to process."))
        buckets = self._lock_and_revalidate()

        SaleOrder = self.env['sale.order'].sudo()
        SaleOrderLine = self.env['sale.order.line'].sudo()
        Allocation = self.env['wujia.compensation.allocation'].sudo()
        created = self.env['sale.order']
        touched = self.env['wujia.return.request']

        # Gom nhóm theo cửa hàng → 1 SO / cửa hàng (BA điểm 5).
        by_franchise = {}
        for g in self.group_ids:
            by_franchise.setdefault(g.franchise_id, self.env[g._name])
            by_franchise[g.franchise_id] |= g

        for franchise, groups in by_franchise.items():
            active = []
            for g in groups:
                if g.delivery_qty <= EPS:
                    continue
                covered = self._delivery_to_claim(
                    g.delivery_qty, g.policy, g.unit_qty, g.claim_uom_id,
                    g.delivery_uom_id)
                if covered > g.total_claim_qty + EPS:
                    raise UserError(_(
                        "Group '%s': delivery qty exceeds the remaining entitlement.",
                        g.compensation_product_id.display_name))
                active.append((g, covered, buckets[self._group_key(g)]))
            if not active:
                continue
            partner = franchise.partner_id
            if not partner:
                raise UserError(_(
                    "Store '%s' has no partner configured for the compensation SO.",
                    franchise.display_name))
            order = SaleOrder.create({
                'partner_id': partner.id,
                'franchise_id': franchise.id,
                'franchise_partner_id': partner.id,
                'is_return_order': True,
                'origin': _('Compensation'),
                'state': 'sent',  # BA STT3 #11: tạo ở 'sent', HQ tự confirm
            })
            created |= order
            for g, covered, reqs in active:
                # Tạo từng dòng SO rồi gắn allocation ngay — không phụ thuộc thứ
                # tự order_line (2 group cùng SP/ĐVT khác policy vẫn map đúng dòng).
                so_line = SaleOrderLine.create({
                    'order_id': order.id,
                    'product_id': g.compensation_product_id.id,
                    'product_uom_qty': g.delivery_qty,
                    'product_uom_id': g.delivery_uom_id.id,
                    'price_unit': 0.0,
                })
                so_line.price_unit = 0.0  # ép 0đ, không theo pricelist (BA điểm 2)
                # FIFO rải trên recordset SỐNG (không đọc g.line_ids: client có thể
                # không gửi sub-list nếu HQ không mở từng nhóm — UAT-BH-001).
                dist = self._fifo_distribute(reqs, covered, g.claim_uom_id)
                for req, alloc_qty in dist:
                    if alloc_qty <= EPS:
                        continue
                    Allocation.create({
                        'request_id': req.id,
                        'sale_order_id': order.id,
                        'sale_order_line_id': so_line.id,
                        'allocated_qty': alloc_qty,
                        'allocation_uom_id': req.approved_uom_id.id,
                    })
                    touched |= req

        if not created:
            raise UserError(_("Could not create the compensation SO (delivery qty = 0)."))
        to_process = touched.filtered(lambda r: r.state == 'approved')
        to_process.write({'state': 'processing'})
        for req in to_process:
            req.message_post(body=_("Compensation SO created, awaiting delivery."))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Compensation sales order'),
            'res_model': 'sale.order',
            'view_mode': 'form' if len(created) == 1 else 'list,form',
            'res_id': created.id if len(created) == 1 else False,
            'domain': [('id', 'in', created.ids)],
        }


class CompensationProcessWizardGroup(models.TransientModel):
    """1 dòng SO bù = (cửa hàng, SP bù, ĐVT giao, chính sách, unit_qty)."""

    _name = 'wujia.compensation.process.wizard.group'
    _description = 'Compensation SO group (wizard)'
    _order = 'id'

    # ⚠️ KHÔNG khai readonly=True ở tầng Python cho field phải sống tới
    # action_confirm: web client BỎ mọi field readonly khi gửi vals lên server
    # (`record.js` _getChanges: readonly && !forceSave → skip) ⇒ wizard được tạo
    # với giá trị rỗng/0 dù default_get tính đúng (UAT-BH-001). Khoá ở VIEW bằng
    # readonly="1" force_save="1".
    wizard_id = fields.Many2one(
        'wujia.compensation.process.wizard', required=True, ondelete='cascade')
    franchise_id = fields.Many2one('wujia.franchise.management', string='Store')
    compensation_product_id = fields.Many2one(
        'product.product', string='Compensation product')
    delivery_uom_id = fields.Many2one('uom.uom', string='Delivery UoM')
    claim_uom_id = fields.Many2one('uom.uom', string='Entitlement UoM')
    policy = fields.Selection(
        [('exact', 'Exact quantity'), ('accumulate', 'Whole-pack accumulation')],
        string='Policy')
    unit_qty = fields.Float(
        string='Entitlement per delivery unit', digits=UOM_DIGITS)
    total_claim_qty = fields.Float(string='Total entitlement', digits=UOM_DIGITS)
    suggested_delivery_qty = fields.Float(
        string='Proposed delivery qty', digits=UOM_DIGITS)
    delivery_qty = fields.Float(string='Delivery qty', digits=UOM_DIGITS)
    line_ids = fields.One2many(
        'wujia.compensation.process.wizard.line', 'group_id', string='Request')


class CompensationProcessWizardLine(models.TransientModel):
    """1 yêu cầu trong nhóm — SL phân bổ FIFO (gợi ý)."""

    _name = 'wujia.compensation.process.wizard.line'
    _description = 'Compensation request line (wizard)'
    _order = 'id'

    # Cùng lý do UAT-BH-001 như model group: readonly chỉ đặt ở view + force_save.
    group_id = fields.Many2one(
        'wujia.compensation.process.wizard.group', required=True, ondelete='cascade')
    request_id = fields.Many2one('wujia.return.request', string='Request')
    request_uom_id = fields.Many2one('uom.uom', string='Entitlement UoM')
    request_remaining_qty = fields.Float(
        string='Qty to compensate', digits=UOM_DIGITS)
    allocate_qty = fields.Float(string='Allocated qty (FIFO)', digits=UOM_DIGITS)
