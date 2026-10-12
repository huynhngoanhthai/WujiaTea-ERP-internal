#!/usr/bin/env bash
# Drop + recreate the WujiaTea DB, install the full module chain,
# and re-run every seed script in the correct order.
#
# Use when:
#   - dev DB is broken (e.g. after destructive schema change),
#   - bootstrapping a fresh prod / staging server.
#
# Does NOT touch git or push anything.
set -euo pipefail

# Đường dẫn tự dò: chạy được trên cả máy Linux lẫn máy Mac mà không sửa file.
# Ghi đè bằng biến môi trường WUJIA_DIR / WUJIA_PYTHON khi cần trỏ chỗ khác.
PROJECT_DIR="${WUJIA_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON="${WUJIA_PYTHON:-/home/huyban/miniconda3/envs/odoo/bin/python}"
if [ ! -x "$PYTHON" ]; then
    for cand in \
        /opt/homebrew/Caskroom/miniconda/base/envs/odoo19/bin/python \
        "$(command -v python3 || true)"; do
        [ -n "$cand" ] && [ -x "$cand" ] && PYTHON="$cand" && break
    done
fi
[ -x "$PYTHON" ] || { echo "Không tìm thấy python — đặt WUJIA_PYTHON=..." >&2; exit 1; }
ODOO_DIR="$("$PYTHON" "${PROJECT_DIR}/scripts/wj_paths.py" --odoo-dir)"
CONFIG="${PROJECT_DIR}/config/odoo.conf"
SCRIPTS="${PROJECT_DIR}/scripts"
DB_NAME="${DB_NAME:-wujia_tea_19}"
PG_HOST="${PG_HOST:-127.0.0.1}"
PG_USER="${PG_USER:-odoo19}"
PG_PASS="${PG_PASS:-1}"

# 21 module — danh sách chuẩn ở docs/wujia-compact-summary.md §2.
# KHÔNG cài wj_ks_dashboard_ninja / wj_ks_dn_advance (workstream dashboard riêng) và
# KHÔNG cài mcp_server. wujia_portal_inspection PHẢI có: thiếu nó thì 4 thẻ metric của
# màn Khảo sát không đo được — đúng chỗ DB dev cũ ở máy Linux bị hụt.
MODULES="wujia_core,wujia_franchise,wujia_sale,wujia_fleet,wujia_delivery,wujia_portal_base,wujia_portal_layout,wujia_portal_sale,wujia_portal_purchase_history,wujia_portal_delivery,wujia_portal_return,wujia_portal_notification,wujia_portal_exam,wujia_portal_knowledge,wujia_portal_report,wujia_portal_support,wujia_portal_info_request,wujia_order_window,wujia_info_request,wujia_knowledge,wujia_support,wujia_notification,wujia_exam,wujia_return,wujia_account,wujia_portal_debt,wujia_portal_inspection"

echo "==> Drop DB ${DB_NAME}"
PGPASSWORD="${PG_PASS}" dropdb -h "${PG_HOST}" -U "${PG_USER}" --if-exists "${DB_NAME}"

echo "==> Create DB ${DB_NAME}"
PGPASSWORD="${PG_PASS}" createdb -h "${PG_HOST}" -U "${PG_USER}" "${DB_NAME}"

echo "==> Install Odoo + modules (no demo data per WujiaTea convention)"
cd "${ODOO_DIR}"
"${PYTHON}" odoo-bin -c "${CONFIG}" -d "${DB_NAME}" \
    -i "${MODULES}" --without-demo=True --stop-after-init

echo "==> Seed admin + franchise"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_admin_franchise.py"

echo "==> Seed fleet demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_fleet_demo.py"

echo "==> Seed products (PHẢI chạy trước portal demo — không có product thì không có đơn hàng)"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_products_demo.py"

echo "==> Seed portal demo (sale orders, picking, batches)"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_portal_demo.py"

echo "==> Seed knowledge demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_knowledge_demo.py"

echo "==> Seed support demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_support_demo.py"

echo "==> Seed exam demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_exam_demo.py"

echo "==> Seed notification demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_notification_demo.py"

echo "==> Seed debt demo"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_debt_demo.py"

echo "==> Seed ui12 demo (knowledge slug ui12-01)"
"${PYTHON}" odoo-bin shell -c "${CONFIG}" -d "${DB_NAME}" --no-http \
    < "${SCRIPTS}/seed_ui12_demo.py"

echo "==> DONE. To verify, run:"
echo "    ${PYTHON} odoo-bin shell -c ${CONFIG} -d ${DB_NAME} --no-http < ${SCRIPTS}/test_sprint5.py"
