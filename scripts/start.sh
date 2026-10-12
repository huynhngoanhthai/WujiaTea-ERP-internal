#!/usr/bin/env bash
# Start Odoo 19 in dev mode for the WujiaTea project.
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

cd "${ODOO_DIR}"
exec "${PYTHON}" odoo-bin -c "${CONFIG}" --dev=xml,qweb,reload "$@"
