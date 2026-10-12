"""J-V7 — câu gốc seed loại thông báo sang EN, giữ bản tiếng Việt (xem legacy_seed.py)."""
import logging

from odoo.addons.wujia_notification.legacy_seed import notification_types_source_to_en

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    changed = notification_types_source_to_en(cr)
    _logger.info("J-V7 post-migrate: %s notification type(s) moved to EN source", changed)
