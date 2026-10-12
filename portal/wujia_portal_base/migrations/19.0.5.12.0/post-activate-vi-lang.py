# Sprint 34 / UI-02: default portal users to Vietnamese so the language control
# reflects the (Vietnamese) portal content. Activates vi_VN and switches existing
# portal-group users to it. Idempotent; scoped to group_portal so backend users
# are left untouched. Runs on `-u wujia_portal_base`.
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Activate vi_VN (only en_US was active) so it is a selectable user language.
    env["res.lang"]._activate_lang("vi_VN")

    portal_group = env.ref("base.group_portal", raise_if_not_found=False)
    if not portal_group:
        return
    # active_test=False so the inactive template portal user (base.template_portal_user_id)
    # is included too — it seeds the lang of every future portal user, so future users
    # default to Vietnamese as well.
    users = env["res.users"].with_context(active_test=False).search(
        [("group_ids", "in", portal_group.id), ("lang", "!=", "vi_VN")]
    )
    if users:
        users.write({"lang": "vi_VN"})
        _logger.info(
            "Sprint34 UI-02: set lang=vi_VN on %s portal user(s)", len(users)
        )
