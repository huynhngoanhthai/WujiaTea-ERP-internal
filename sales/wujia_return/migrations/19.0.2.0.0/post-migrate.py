"""J-V6 — câu gốc seed loại lỗi sang EN, giữ bản tiếng Việt (xem legacy_seed.py)."""
import logging

from odoo.addons.wujia_return.legacy_seed import issue_types_source_to_en

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    changed = issue_types_source_to_en(cr)
    _logger.info("J-V6 post-migrate: %s issue-type field(s) moved to EN source", changed)
