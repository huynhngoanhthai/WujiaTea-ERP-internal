#!/usr/bin/env bash
# Upgrade Wujia modules without dropping the DB.
# Usage: ./scripts/upgrade.sh                # upgrade wujia_core,wujia_franchise
#        ./scripts/upgrade.sh wujia_franchise  # upgrade specific module(s)
set -euo pipefail

# Đường dẫn tự dò như start.sh; ghi đè bằng WUJIA_DIR / WUJIA_PYTHON / WUJIA_ODOO / DB_NAME.
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
DB_NAME="${DB_NAME:-wujia_tea_19}"

MODULES="${1:-wujia_core,wujia_franchise}"

cd "${ODOO_DIR}"
exec "${PYTHON}" odoo-bin -c "${CONFIG}" -d "${DB_NAME}" -u "${MODULES}" --stop-after-init
