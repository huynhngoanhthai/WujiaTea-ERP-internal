# UI-02 (cluster B): re-run the Sprint 34 vi_VN backfill.
#
# 19.0.5.12.0 already did this once, but it only ran that one time: portal accounts
# created afterwards took their language from whoever created them, and since
# Sprint 44 the backend runs in English. res_users.create() now closes the leak for
# new accounts; this sweep fixes the ones already created. Idempotent and scoped to
# base.group_portal, so backend users keep their language.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.lang"]._activate_lang("vi_VN")

    portal_group = env.ref("base.group_portal", raise_if_not_found=False)
    if not portal_group:
        return
    # active_test=False keeps base.template_portal_user_id in scope — it seeds every
    # user the portal wizard creates.
    users = env["res.users"].with_context(active_test=False).search(
        [("group_ids", "in", portal_group.id), ("lang", "!=", "vi_VN")]
    )
    if not users:
        _logger.info("UI-02: portal users already on vi_VN, nothing to backfill")
        return
    _logger.info(
        "UI-02: set lang=vi_VN on %s portal user(s): %s",
        len(users), ", ".join(users.mapped("login")),
    )
    users.write({"lang": "vi_VN"})
