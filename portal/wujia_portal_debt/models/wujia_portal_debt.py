"""Nguồn dữ liệu DUY NHẤT của module Công nợ portal.

`AbstractModel` — không bảng, không migration. Toàn bộ controller + 2 template
inherit (badge sheet "Thêm", KPI Home) đều lấy số qua `get_summary()` /
`get_payments()` / `get_bank_info()` / `get_shell_badge()`, nên khi wire backend thật
chỉ đổi phần dựng dict trong file này, template KHÔNG đụng một dòng.

**Wire backend thật — Sprint 48 (BA task Tasks!STT9, Controller CT-050..CT-055):**
Đọc `account.move` (out_invoice/out_refund) + `account.payment` scope theo
`franchise_id` (3 field custom ở module `wujia_account`). Mọi query bằng `sudo()` +
domain franchise tường minh — portal user KHÔNG có ACL account, và KHÔNG tin store do
client truyền (controller resolve franchise từ session).

⚠️ PERF 1500 user: `get_shell_badge()` chạy trên MỌI trang mobile ⇒ đọc thẳng 2 field
store `portal_overdue_invoice_count` / `portal_debt_remaining` trên franchise (0 query;
cập nhật bằng cron daily + hook ở `wujia_account`). TUYỆT ĐỐI không search on-the-fly ở đây.

Kiểu dữ liệu template phụ thuộc (giữ nguyên): `date`/`due`/`nearest_due`/`confirmed_date`
là `datetime.date` (template gọi `.strftime`); `status` ∈ overdue/unpaid/partial/paid;
`state` ∈ outstanding/partial/paid/empty.
"""

from datetime import date, timedelta

from odoo import api, fields, models
from odoo.tools import float_compare, float_is_zero
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.utils import portal_money, status_badge_for

_lt = LazyTranslate(__name__)

# Số tuần / kỳ đổ vào dropdown bộ lọc (kỳ hiện tại + 5 kỳ trước).
WEEK_CHOICES = 6
MONTH_CHOICES = 6

# Mặc định hiển thị 2 hoá đơn, phần còn lại bung bằng `?all=1` (Figma: "Hiển thị 2/4 hóa đơn").
INVOICE_PREVIEW = 2

# Nhãn + variant badge cho state tổng (Figma 02/03/04); variant từ nguồn chung CMP-SB-001.
# Nhãn là `_lt` (J-V5): câu EN phải có trong `_STATUS_TERMS_BY_VARIANT` của portal_base
# để giữ màu; controller dịch theo người xem qua `translated_badges()`.
STATE_BADGE = {k: (v, status_badge_for(v)) for k, v in {
    'outstanding': _lt('Has overdue'),
    'partial': _lt('Partially paid'),
    'unpaid': _lt('Unpaid'),
    'credit': _lt('Credit balance'),
    'paid': _lt('Paid'),
}.items()}

# Nhãn + variant badge cho từng hoá đơn.
INVOICE_BADGE = {k: (v, status_badge_for(v)) for k, v in {
    'overdue': _lt('Overdue'),
    'unpaid': _lt('Unpaid'),
    'partial': _lt('Partial'),
    'credit': _lt('Credit note'),
    'paid': _lt('Paid'),
}.items()}


def translated_badges(env, badges):
    """`{key: (nhãn đã dịch theo env.lang, class)}` cho template — QWeb không tự dịch `_lt`
    ngoài request, và gán biến trước khi `env._` để trình trích `.pot` không đẻ msgid rác."""
    result = {}
    for key, (label, css) in badges.items():
        result[key] = (env._(label), css)
    return result

# Chứng từ công nợ khách hàng của cửa hàng: hoá đơn + credit note đã ghi sổ.
_DEBT_MOVE_TYPES = ('out_invoice', 'out_refund')
# Payment đã xác nhận (Odoo 19): loại draft/canceled/rejected.
_CONFIRMED_PAYMENT_STATES = ('in_process', 'paid')
# payment_state coi như đã tất toán (không còn nợ).
_SETTLED_PAYMENT_STATES = ('paid', 'in_payment', 'reversed')


def _monday(day):
    """Thứ Hai của tuần chứa `day` (ISO: tuần Mon→Sun)."""
    return day - timedelta(days=day.weekday())


def _week_key(monday):
    """Khoá tuần dùng trên URL — ISO 'YYYY-Www', so sánh/parse được, không phụ thuộc locale."""
    iso = monday.isocalendar()
    return '%04d-W%02d' % (iso[0], iso[1])


def _start_of_month(day):
    return day.replace(day=1)


def _end_of_month(day):
    """Ngày cuối tháng chứa `day` (khỏi cần dateutil)."""
    first_next_month = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first_next_month - timedelta(days=1)


# Hậu tố bậc tiền rút gọn (J-V5) — vi_VN: tỷ / tr / k.
_UNIT_BILLION = _lt('%sB')
_UNIT_MILLION = _lt('%sM')
_UNIT_THOUSAND = _lt('%sK')


def _unit(env, unit):
    """Hậu tố đã dịch theo `env.lang`; không có env ⇒ câu gốc EN."""
    return env._(unit) if env is not None else unit._source


def _one_decimal(value, point=','):
    """12.65 → '12,7'; 1.0 → '1' — cắt đuôi '.0' trước khi đổi dấu thập phân."""
    text = '%.1f' % value
    return (text[:-2] if text.endswith('.0') else text).replace('.', point)


def _short_amount(amount, symbol='', env=None):
    """Tiền rút gọn cho tile KPI Home (ô hẹp, 4 tile/hàng): 12.650.000 → '12,7tr'.

    Bậc tính theo TRỊ TUYỆT ĐỐI rồi gắn lại dấu: số âm (trả thừa / credit note) trước
    đây rớt qua cả hai bậc nên in nguyên '-72449 $' và bị bẻ xuống 2 dòng ở ô hẹp
    (UI-MOB-HOME-004). Ký hiệu truyền từ ngoài (currency của công ty), không hardcode
    '₫' — cùng luật với cụm D: portal không được tự quyết đơn vị tiền.

    J-V5: hậu tố bậc + dấu thập phân theo ngôn ngữ của `env` (vi_VN: '12,7tr', '1tỷ';
    en_US: '12.7M', '1B'). Không có `env` ⇒ câu gốc EN, dấu '.'."""
    point = '.'
    if env is not None and env.lang:
        point = env['res.lang']._get_data(code=env.lang).decimal_point or '.'
    amount = amount or 0
    sign = '-' if amount < 0 else ''
    value = abs(amount)
    if value >= 10 ** 9:
        return sign + _unit(env, _UNIT_BILLION) % _one_decimal(value / 1000000000.0, point)
    if value >= 1000000:
        text = _one_decimal(value / 1000000.0, point)
        # 999.999.999 làm tròn một chữ số thành '1000' ⇒ lên bậc, khỏi in '1000M'.
        return sign + (_unit(env, _UNIT_BILLION) % '1' if text == '1000'
                       else _unit(env, _UNIT_MILLION) % text)
    if value >= 1000:
        return sign + _unit(env, _UNIT_THOUSAND) % (value // 1000)
    return ('%s%d %s' % (sign, value, symbol)).strip()


def _week_label(monday):
    """Nhãn Figma: '08/07 – 14/07/2026'."""
    sunday = monday + timedelta(days=6)
    return '%s – %s' % (monday.strftime('%d/%m'), sunday.strftime('%d/%m/%Y'))


class WujiaPortalDebt(models.AbstractModel):
    _name = 'wujia.portal.debt'
    _description = 'Wujia Portal — debt & payment data source'

    # ------------------------------------------------------------------
    # Tuần
    # ------------------------------------------------------------------
    @api.model
    def _week_options(self, today=None):
        """Danh sách tuần cho dropdown, mới nhất trước."""
        today = today or date.today()
        first = _monday(today)
        return [
            {
                'key': _week_key(first - timedelta(weeks=i)),
                'label': _week_label(first - timedelta(weeks=i)),
                'monday': first - timedelta(weeks=i),
                'offset': i,
            }
            for i in range(WEEK_CHOICES)
        ]

    @api.model
    def _resolve_week(self, week=None, today=None, franchise_id=None):
        """`?week=` → option tương ứng. Sai/thiếu → tuần MẶC ĐỊNH theo nghiệp vụ.

        Không bao giờ raise: bộ lọc là query param người dùng sửa được tay."""
        options = self._week_options(today=today)
        if week:
            for opt in options:
                if opt['key'] == week:
                    return opt, options
        return self._default_week(options, franchise_id, today=today), options

    @api.model
    def _default_week(self, options, franchise_id, today=None):
        """Tuần mở sẵn khi URL không có `?week=` (WJ-DEBT-010).

        Ưu tiên: tuần quá hạn CŨ NHẤT còn dư → tuần liền trước nếu có hoá đơn →
        tuần hiện tại. Công nợ tuần N đến hạn thứ Năm tuần N+1 nên tuần hiện tại
        gần như luôn chưa cần xử lý.

        ⚠️ PERF: MỘT `search_read` cho cả 6 tuần rồi gộp trong Python — không lặp
        `get_summary` theo tuần (6 query/lượt mở trang × 1500 user)."""
        if not franchise_id:
            return options[0]
        today = today or date.today()
        oldest = options[-1]['monday']
        rows = self.env['account.move'].sudo().search_read([
            ('franchise_id', '=', franchise_id),
            ('move_type', 'in', _DEBT_MOVE_TYPES),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', oldest),
            ('invoice_date', '<=', options[0]['monday'] + timedelta(days=6)),
        ], ['invoice_date', 'invoice_date_due', 'move_type', 'amount_residual'])
        if not rows:
            return options[0]
        seen, overdue = set(), set()
        for row in rows:
            key = _week_key(_monday(row['invoice_date']))
            seen.add(key)
            due = row['invoice_date_due'] or row['invoice_date']
            if (row['move_type'] == 'out_invoice' and row['amount_residual'] > 0
                    and due < today):
                overdue.add(key)
        for opt in reversed(options):          # cũ nhất trước
            if opt['key'] in overdue:
                return opt
        if len(options) > 1 and options[1]['key'] in seen:
            return options[1]
        return options[0]

    @api.model
    def _currency_of(self, records=None):
        """Currency của một tập chứng từ (move hoặc payment) — dùng chung cho mọi màn.

        Cùng một currency → lấy currency đó; rỗng hoặc pha trộn → currency công ty
        (khối nào cần tách từng loại tiền thì tự nhóm, xem `_group_totals`)."""
        if records:
            currencies = records.mapped('currency_id')
            if len(currencies) == 1:
                return currencies
        return self.env.company.currency_id

    @api.model
    def _money_keys(self, records=None):
        """2 key currency mà mọi payload trả về (template bind vào `vnd()`)."""
        currency = self._currency_of(records)
        return {
            'currency_symbol': currency.symbol or '',
            'currency_decimals': currency.decimal_places or 0,
        }

    # ------------------------------------------------------------------
    # Summary — điểm nối duy nhất giữa UI và backend kế toán (CT-050/051/052)
    # ------------------------------------------------------------------
    @api.model
    def get_summary(self, franchise_id, week=None, today=None):
        """Số liệu công nợ của 1 cửa hàng trong 1 tuần (Mon→Sun theo `invoice_date`).

        :param franchise_id: id `wujia.franchise.management` (0/False = chưa chọn cửa hàng)
        :param week: khoá tuần 'YYYY-Www'; sai hoặc None → tuần hiện tại
        :return: dict — luôn đủ key kể cả state 'empty', để template không phải `.get()`.
        """
        opt, options = self._resolve_week(week, today=today, franchise_id=franchise_id)
        monday = opt['monday']
        base = {
            'franchise_id': franchise_id or False,
            'franchise_code': self._franchise_code(franchise_id),
            'week_key': opt['key'],
            'week_label': opt['label'],
            'week_number': monday.isocalendar()[1],
            'week_short': '%s – %s' % (
                monday.strftime('%d/%m'), (monday + timedelta(days=6)).strftime('%d/%m')),
            'weeks': [{'key': w['key'], 'label': w['label']} for w in options],
        }
        if not franchise_id:
            # Chưa chọn cửa hàng → empty state, KHÔNG 500 (guard controller).
            base.update(self._empty_payload())
            return base
        base.update(self._week_payload(franchise_id, monday, today=today))
        return base

    @api.model
    def get_shell_badge(self):
        """Số liệu cho 2 điểm vào ở shell: badge sheet "Thêm" + tile KPI Home.

        ⚠️ Gọi trên MỌI trang mobile ⇒ đọc thẳng 2 field STORE trên franchise (0 query).
        Nguồn cập nhật: cron daily + hook account.move/account.payment (module wujia_account)."""
        try:
            from odoo.addons.wujia_portal_base.controllers.portal import (
                get_active_franchise_id,
            )
            franchise_id = get_active_franchise_id()
        except Exception:  # noqa: BLE001 — render backend/cron: không có request
            franchise_id = False
        symbol = self.env.company.currency_id.symbol or ''
        if not franchise_id:
            return {'overdue_count': 0, 'remaining': 0,
                    'remaining_label': _short_amount(0, symbol, self.env),
                    'currency_symbol': symbol,
                    'currency_decimals': self.env.company.currency_id.decimal_places or 0}
        franchise = self.env['wujia.franchise.management'].sudo().browse(franchise_id).exists()
        remaining = franchise.portal_debt_remaining or 0
        # Nợ sinh ra từ hoá đơn của chính các đơn cửa hàng đặt ⇒ currency của nó là
        # currency bảng giá cửa hàng, không phải của công ty. Cửa hàng bán bằng USD
        # trong công ty VND thì tile này từng in số USD kèm ký hiệu ₫ (cụm D).
        # Đọc pricelist qua record đã browse sẵn — không thêm query cho mỗi trang mobile.
        store_currency = (franchise.partner_id.property_product_pricelist.currency_id
                          if franchise.partner_id else False) or self.env.company.currency_id
        symbol = store_currency.symbol or ''
        return {
            'overdue_count': franchise.portal_overdue_invoice_count or 0,
            'remaining': remaining,
            'remaining_label': _short_amount(remaining, symbol, self.env),
            'currency_symbol': symbol,
            'currency_decimals': store_currency.decimal_places or 0,
        }

    @api.model
    def get_home_debt_kpi(self):
        """Tile KPI Công nợ ở Home mobile — phân biệt "chưa có dữ liệu" với 0đ thật.

        `portal_debt_remaining` = 0 ở CẢ hai trường hợp: cửa hàng chưa hề có chứng từ
        kế toán, và cửa hàng đã trả hết. In "0 đ" cho trường hợp đầu là sai nghĩa kế
        toán (STT11 acceptance #5) ⇒ đếm thêm 1 lần xem có chứng từ nào không.

        ⚠️ CHỈ Home gọi (1 lần/trang, `franchise_id` store+index, `limit=1`).
        Shell/bottomnav vẫn dùng `get_shell_badge()` để giữ 0 query trên mọi trang."""
        badge = self.get_shell_badge()
        try:
            from odoo.addons.wujia_portal_base.controllers.portal import (
                get_active_franchise_id,
            )
            franchise_id = get_active_franchise_id()
        except Exception:  # noqa: BLE001 — render backend/cron: không có request
            franchise_id = False
        has_data = bool(franchise_id) and bool(self.env['account.move'].sudo().search_count([
            ('franchise_id', '=', franchise_id),
            ('move_type', 'in', _DEBT_MOVE_TYPES),
            ('state', '=', 'posted'),
        ], limit=1))
        badge['has_data'] = has_data
        if not has_data:
            badge['remaining_label'] = '—'
        return badge

    # ------------------------------------------------------------------
    # Kỳ thanh toán (màn 06) — CT-054
    # ------------------------------------------------------------------
    @api.model
    def _month_options(self, today=None):
        """Danh sách kỳ cho dropdown "Thời gian thanh toán", mới nhất trước.

        Figma vẽ 1 dòng "01/07 – 31/07/2026" ⇒ kỳ = trọn tháng (1 control native,
        dùng chung component filter + JS auto-submit với bộ lọc tuần)."""
        first = (today or date.today()).replace(day=1)
        options = []
        for _i in range(MONTH_CHOICES):
            last = _end_of_month(first)
            options.append({
                'key': first.strftime('%Y-%m'),
                'label': '%s – %s' % (first.strftime('%d/%m'), last.strftime('%d/%m/%Y')),
                'date_from': first,
                'date_to': last,
            })
            first = _start_of_month(first - timedelta(days=1))
        return options

    @api.model
    def _resolve_month(self, month=None, today=None):
        """`?month=YYYY-MM` → option. Sai/thiếu → tháng hiện tại. Không bao giờ raise."""
        options = self._month_options(today=today)
        if month:
            for opt in options:
                if opt['key'] == month:
                    return opt, options
        return options[0], options

    @api.model
    def get_payments(self, franchise_id, month=None, date_from=None, date_to=None, today=None,
                     keyword=None):
        """Lịch sử thanh toán đã xác nhận trong 1 kỳ (Figma màn 06, CT-054).

        Ưu tiên `month` (dropdown). `date_from`/`date_to` vẫn nhận được để BA/FE
        gọi khoảng tuỳ ý sau này. Mặc định = tháng hiện tại. `keyword` (PC STT10):
        lọc theo mã/nội dung thanh toán — mobile không truyền nên hành vi cũ không đổi."""
        opt, options = self._resolve_month(month, today=today)
        date_from = date_from or opt['date_from']
        date_to = date_to or opt['date_to']
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        payments, records = (self._query_payments(franchise_id, date_from, date_to,
                                                  keyword=keyword)
                             if franchise_id else ([], None))
        totals = self._group_totals(payments)
        payload = {
            'month_key': opt['key'],
            'months': [{'key': m['key'], 'label': m['label']} for m in options],
            'date_from': date_from,
            'date_to': date_to,
            'range_label': '%s – %s' % (
                date_from.strftime('%d/%m'), date_to.strftime('%d/%m/%Y')),
            'payments': payments,
            # Kỳ nhiều loại tiền thì KHÔNG có một tổng duy nhất (WJ-DEBT-004) —
            # `total` chỉ còn nghĩa khi cả kỳ cùng một currency; UI đọc `totals`.
            'total': totals[0]['amount'] if len(totals) == 1 else 0,
            'totals': totals,
        }
        payload.update(self._money_keys(records))
        return payload

    @api.model
    def _group_totals(self, payments):
        """Tổng đã xác nhận TÁCH THEO TỪNG LOẠI TIỀN (chủ dự án chốt 14/08: không quy
        đổi tỷ giá, không cộng số khác currency)."""
        buckets = {}
        for pay in payments:
            key = (pay['currency_symbol'], pay['currency_decimals'])
            buckets[key] = buckets.get(key, 0.0) + pay['amount']
        return [{'symbol': symbol, 'decimals': decimals, 'amount': amount,
                 'label': portal_money(amount, symbol, decimals)}
                for (symbol, decimals), amount in buckets.items()]

    @api.model
    def get_bank_info(self, franchise_id, amount, week_number):
        """Thông tin chuyển khoản (Figma màn 07, CT-055).

        Lấy tài khoản nhận tiền của company hiện hành có `portal_payment_enabled=True`,
        sequence nhỏ nhất. Backend tự tính nội dung CK từ mã cửa hàng + tuần + số tiền
        (KHÔNG tin giá trị portal gửi lên). Mở QR chỉ trả hướng dẫn — không tạo payment.

        ⚠️ Ảnh QR (tĩnh/động) BA CHƯA chốt (CT-055 cột ghi chú còn để ngỏ) ⇒ chỉ trả
        STK + nội dung, defer ảnh QR (Need BA Confirm).

        `configured` = có tài khoản hợp lệ hay không; template rẽ theo cờ này thay vì
        đoán từ chuỗi rỗng (WJ-DEBT-002)."""
        bank = self._portal_bank_account()
        if not bank:
            return {
                'configured': False,
                'name': '',
                'holder': '',
                'account': '',
                'memo': '',
            }
        return {
            'configured': True,
            'name': bank.bank_id.name or bank.bank_name or self.env._('Bank'),
            'holder': bank.acc_holder_name or bank.partner_id.name or '',
            'account': bank.acc_number or '',
            # Số âm (tuần dư có) không bao giờ được lọt vào nội dung CK — WJ-DEBT-007.
            'memo': '%s K%s %s' % (
                self._franchise_code(franchise_id), week_number, max(int(amount or 0), 0)),
        }

    # ------------------------------------------------------------------
    # Query backend thật (sudo + scope franchise)
    # ------------------------------------------------------------------
    @api.model
    def _franchise_code(self, franchise_id):
        if not franchise_id:
            return 'H000'
        franchise = self.env['wujia.franchise.management'].sudo().browse(franchise_id)
        return franchise.exists().code or 'H000'

    @api.model
    def _empty_substate(self, franchise_id):
        """PC STT10 (rule 10c/10d) — chỉ gọi khi tuần đang chọn KHÔNG có hoá đơn:
        'empty_week' nếu cửa hàng còn công nợ ở kỳ khác, 'no_debt' nếu hết nợ mọi kỳ.

        ⚠️ Đọc field STORE `portal_debt_remaining` (stored, cron+hook cập nhật ở
        wujia_account) → 0 query on-the-fly, đúng perf-first 1500 user (cùng nguồn
        với get_shell_badge). Mobile KHÔNG dùng — giữ nguyên 1 empty state cũ."""
        if not franchise_id:
            return 'no_debt'
        franchise = self.env['wujia.franchise.management'].sudo().browse(franchise_id).exists()
        return 'empty_week' if (franchise.portal_debt_remaining or 0) > 0 else 'no_debt'

    @api.model
    def _empty_payload(self):
        payload = {
            'state': 'empty',
            'total': 0,
            'paid': 0,
            'remaining': 0,
            'amount_due': 0,
            'credit_amount': 0,
            'invoice_count': 0,
            'has_overdue': False,
            'overdue_count': 0,
            'nearest_due': False,
            'confirmed_date': False,
            'payment_due_date': False,
            'payment_due_label': '-',
            'invoices': [],
        }
        payload.update(self._money_keys())
        return payload

    @api.model
    def _invoice_status(self, move, today):
        """Trạng thái Portal của 1 chứng từ, suy từ payment_state + số dư + hạn (CT-051).
        Không tạo trạng thái kế toán mới."""
        rounding = move.currency_id.rounding or 0.01
        residual = move.amount_residual
        if float_is_zero(residual, precision_rounding=rounding) or residual < 0 \
                or move.payment_state in _SETTLED_PAYMENT_STATES:
            return 'paid'
        # Giấy báo có còn dư = tiền cửa hàng ĐƯỢC trừ, không phải nợ (WJ-DEBT-007).
        if move.move_type == 'out_refund':
            return 'credit'
        if move.invoice_date_due and move.invoice_date_due < today:
            return 'overdue'
        # 'Một phần' chỉ khi đã trả được một ít (WJ-DEBT-001) — payment_state của Odoo
        # có thể là 'partial' do khớp một dòng lẻ mà số tiền chưa giảm.
        if float_compare(residual, move.amount_total,
                         precision_rounding=rounding) < 0:
            return 'partial'
        return 'unpaid'

    @api.model
    def _week_payload(self, franchise_id, monday, today=None):
        """Số liệu 1 tuần từ account.move thật. Credit note (out_refund) giảm công nợ:
        total/paid/remaining là số RÒNG (hoá đơn − credit note)."""
        today = today or date.today()
        sunday = monday + timedelta(days=6)
        moves = self.env['account.move'].sudo().search([
            ('franchise_id', '=', franchise_id),
            ('move_type', 'in', _DEBT_MOVE_TYPES),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', monday),
            ('invoice_date', '<=', sunday),
        ], order='invoice_date, id')
        if not moves:
            return self._empty_payload()

        total = paid = remaining = 0.0
        overdue_count = 0
        due_dates = []
        invoices = []
        for move in moves:
            sign = -1.0 if move.move_type == 'out_refund' else 1.0
            total += sign * move.amount_total
            remaining += sign * move.amount_residual
            status = self._invoice_status(move, today)
            if status == 'overdue':
                overdue_count += 1
                if move.invoice_date_due:
                    due_dates.append(move.invoice_date_due)
            # Số dòng: còn dư → hiển thị số dư; đã tất toán → tổng. Credit note âm.
            line_amount = move.amount_residual if move.amount_residual > 0 else move.amount_total
            # PC (STT10): bảng cần 3 số/hoá đơn (Tổng / Đã trả / Còn phải trả). Additive —
            # mobile bỏ qua các key này; giữ dấu `sign` nhất quán với tổng tuần (credit note âm).
            inv_total = sign * move.amount_total
            inv_remaining = sign * (move.amount_residual if move.amount_residual > 0 else 0.0)
            invoices.append({
                'name': move.name or move.ref or '—',
                'date': move.invoice_date,
                'due': move.invoice_date_due or move.invoice_date,
                'status': status,
                'amount': sign * line_amount,
                'total': inv_total,
                'paid': inv_total - inv_remaining,
                'remaining': inv_remaining,
            })
        paid = total - remaining
        state = self._week_state(total, remaining, overdue_count,
                                 self._currency_of(moves).rounding or 0.01)
        due_date = monday + timedelta(days=10)   # thứ Năm tuần kế (BA: tuần N → thứ 5 tuần N+1)

        payload = {
            'state': state,
            'total': total,
            'paid': paid,
            'remaining': remaining,
            # Số ĐƯA RA UI: nợ không bao giờ âm, phần âm là dư có (WJ-DEBT-007).
            'amount_due': max(remaining, 0.0),
            'credit_amount': max(-remaining, 0.0),
            'invoice_count': len(invoices),
            'has_overdue': overdue_count > 0,
            'overdue_count': overdue_count,
            'nearest_due': min(due_dates) if due_dates else False,
            'confirmed_date': self._confirmed_date(moves) if state == 'paid' else False,
            'payment_due_date': due_date,
            'payment_due_label': due_date.strftime('%d/%m/%Y'),
            'invoices': invoices,
        }
        payload.update(self._money_keys(moves))
        return payload

    @api.model
    def _week_state(self, total, remaining, overdue_count, rounding):
        """State của card tổng quan — CÙNG luật với `_invoice_status` để card và dòng
        chứng từ không bao giờ nói khác nhau (WJ-DEBT-001)."""
        if float_is_zero(remaining, precision_rounding=rounding):
            return 'paid'
        if remaining < 0:
            return 'credit'          # dư có: credit note lớn hơn nợ (WJ-DEBT-007)
        if overdue_count > 0:
            return 'outstanding'
        if float_compare(remaining, total, precision_rounding=rounding) < 0:
            return 'partial'
        return 'unpaid'

    @api.model
    def _confirmed_date(self, moves):
        """Ngày Ngô Gia xác nhận (state 'paid'): ngày payment đối soát mới nhất của các
        chứng từ trong tuần; fallback ngày hoá đơn mới nhất."""
        payments = moves.reconciled_payment_ids.filtered('date')
        if payments:
            return max(payments.mapped('date'))
        inv_dates = [m.invoice_date for m in moves if m.invoice_date]
        return max(inv_dates) if inv_dates else False

    @api.model
    def _payment_time(self, payment):
        """account.payment.date là Date (không giờ) → lấy giờ từ create_date theo tz user."""
        if not payment.create_date:
            return ''
        local_dt = fields.Datetime.context_timestamp(payment, payment.create_date)
        return local_dt.strftime('%H:%M')

    @api.model
    def _query_payments(self, franchise_id, date_from, date_to, keyword=None):
        """Payment đã xác nhận của cửa hàng trong kỳ (CT-054). Chi ngược (outbound) hiển
        thị số âm để không cộng nhầm vào "đã trả" (BA §6).

        `keyword` (PC): lọc thêm theo mã payment (`name`) hoặc nội dung (`memo`).
        Trả `(list dict, recordset)` — recordset để gọi `_money_keys` mà khỏi query lại."""
        domain = [
            ('franchise_id', '=', franchise_id),
            ('state', 'in', _CONFIRMED_PAYMENT_STATES),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        kw = (keyword or '').strip()
        if kw:
            domain += ['|', ('name', 'ilike', kw), ('memo', 'ilike', kw)]
        payments = self.env['account.payment'].sudo().search(domain, order='date desc, id desc')
        result = []
        for payment in payments:
            sign = -1.0 if payment.payment_type == 'outbound' else 1.0
            amount = sign * payment.amount
            # Tiền của CHÍNH giao dịch, không phải của công ty (WJ-DEBT-004).
            currency = payment.currency_id or self.env.company.currency_id
            symbol, decimals = currency.symbol or '', currency.decimal_places or 0
            result.append({
                'ref': payment.name or '—',
                'date': payment.date,
                'time': self._payment_time(payment),
                'method': payment.journal_id.name or self.env._('Bank transfer'),
                'trace': payment.memo or payment.name or '',
                'amount': amount,
                'currency_symbol': symbol,
                'currency_decimals': decimals,
                'amount_label': portal_money(amount, symbol, decimals),
                'state': 'confirmed',
            })
        return result, payments

    @api.model
    def _portal_bank_account(self):
        """TK nhận tiền của company hiện hành, bật portal, sequence nhỏ nhất (CT-055)."""
        company = self.env.company
        return self.env['res.partner.bank'].sudo().search([
            ('id', 'in', company.bank_ids.ids),
            ('portal_payment_enabled', '=', True),
        ], order='sequence, id', limit=1)
