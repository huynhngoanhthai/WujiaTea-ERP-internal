"""WJ-ORD-004: bật extension `unaccent` để search sản phẩm bỏ dấu.

Odoo tự bọc `unaccent()` quanh toán tử ilike khi registry phát hiện hàm
`unaccent` tồn tại (Registry.has_unaccent) — nên chỉ cần đảm bảo extension đã
cài, domain `('name','ilike',keyword)` sẵn có sẽ thành accent-insensitive sau
khi server khởi động lại.

CREATE EXTENSION cần quyền superuser DB. Nếu role không đủ quyền → bỏ qua trong
savepoint (search vẫn chạy, chỉ không bỏ dấu) và log cảnh báo, KHÔNG làm hỏng
cả lần upgrade.

Ghi chú (giải trình cho BA/GPT — index unaccent chủ động KHÔNG tạo):
`unaccent()` mặc định KHÔNG IMMUTABLE và `name` là field dịch (jsonb) nên không
thể tạo functional index `unaccent(name)` trực tiếp (đây cũng là lý do Odoo core
không tự tạo index unaccent). Catalog portal có giới hạn (search_count + limit
24/trang) nên chi phí seq-scan không đáng kể — không bổ sung index ở bước này.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SAVEPOINT wj_ord_004_unaccent")
    try:
        cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    except Exception as exc:  # noqa: BLE001 — thiếu quyền DB là non-fatal
        cr.execute("ROLLBACK TO SAVEPOINT wj_ord_004_unaccent")
        _logger.warning(
            "WJ-ORD-004: could not create the unaccent extension (%s). "
            "Product search still works but without accent folding.", exc,
        )
    else:
        cr.execute("RELEASE SAVEPOINT wj_ord_004_unaccent")
        _logger.info("WJ-ORD-004: unaccent extension is ready.")
