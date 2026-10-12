# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Promote standard accounting users to the new ERP Heritage groups.

In 19.0.1.0.1 the suite's ACL CSVs were rewritten to require
eh_account_base.group_eh_user (or _manager) instead of the upstream
account.group_account_user / _manager. Without this migration script,
every existing user who only had the standard accounting role would
lose access to every ERP Heritage record on upgrade.

The script runs after data has loaded so the new group records exist,
and copies every member of account.group_account_user into
eh_account_base.group_eh_user, and every member of account.group_
account_manager into eh_account_base.group_eh_manager. ON CONFLICT
DO NOTHING keeps the script idempotent: re-running it is safe.

Direct SQL avoids ORM bootstrapping inside migrations, which is
more reliable in upgrade contexts.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install: nothing to migrate. The ACL change takes effect
        # against the new groups, which start empty and are populated by
        # the admin assigning users.
        return

    cr.execute(
        """
        SELECT id FROM ir_model_data
        WHERE module = 'eh_account_base'
          AND name IN ('group_eh_user', 'group_eh_manager')
        """,
    )
    if cr.rowcount < 2:
        _logger.warning(
            "eh_account_base 19.0.1.0.1 migration: new groups not yet "
            "loaded, skipping promotion. Re-run upgrade.",
        )
        return

    cr.execute(
        """
        WITH src AS (
            SELECT res_id AS gid
            FROM ir_model_data
            WHERE module = 'account'
              AND name = 'group_account_user'
        ), dst AS (
            SELECT res_id AS gid
            FROM ir_model_data
            WHERE module = 'eh_account_base'
              AND name = 'group_eh_user'
        )
        INSERT INTO res_groups_users_rel (gid, uid)
        SELECT dst.gid, rel.uid
        FROM res_groups_users_rel rel, src, dst
        WHERE rel.gid = src.gid
        ON CONFLICT DO NOTHING
        """,
    )
    user_promoted = cr.rowcount

    cr.execute(
        """
        WITH src AS (
            SELECT res_id AS gid
            FROM ir_model_data
            WHERE module = 'account'
              AND name = 'group_account_manager'
        ), dst AS (
            SELECT res_id AS gid
            FROM ir_model_data
            WHERE module = 'eh_account_base'
              AND name = 'group_eh_manager'
        )
        INSERT INTO res_groups_users_rel (gid, uid)
        SELECT dst.gid, rel.uid
        FROM res_groups_users_rel rel, src, dst
        WHERE rel.gid = src.gid
        ON CONFLICT DO NOTHING
        """,
    )
    manager_promoted = cr.rowcount

    _logger.info(
        "eh_account_base 19.0.1.0.1: promoted %d users to "
        "group_eh_user and %d users to group_eh_manager.",
        user_promoted, manager_promoted,
    )
