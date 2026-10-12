# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Install / upgrade hooks for eh_account_base.

Auto-promotes accounting users to the suite-specific privilege groups so
that a fresh install does not leave admin and existing accountants with
"You are not allowed to access ..." errors on every EH model. The
migration script at migrations/19.0.1.0.1/post-migration.py handles
the upgrade path; this hook covers the fresh-install path.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Promote admin + existing account users into EH groups on install.

    Three groups are seeded:
      - eh_account_base.group_eh_user: every member of
        account.group_account_user, plus the admin user.
      - eh_account_base.group_eh_manager: every member of
        account.group_account_manager, plus the admin user.
      - eh_account_base.group_eh_auditor: only the admin user (opt-in
        for everyone else).

    The hook is idempotent: writing the same membership twice is a
    no-op at the m2m level.
    """
    _ensure_partner(env)
    user_group = env.ref(
        'eh_account_base.group_eh_user', raise_if_not_found=False,
    )
    manager_group = env.ref(
        'eh_account_base.group_eh_manager', raise_if_not_found=False,
    )
    auditor_group = env.ref(
        'eh_account_base.group_eh_auditor', raise_if_not_found=False,
    )
    if not user_group or not manager_group:
        _logger.warning(
            "eh_account_base post_init: privilege groups not found, "
            "skipping auto-promotion."
        )
        return

    upstream_user = env.ref(
        'account.group_account_user', raise_if_not_found=False,
    )
    upstream_manager = env.ref(
        'account.group_account_manager', raise_if_not_found=False,
    )

    Users = env['res.users'].sudo()

    # Promote every account.group_account_user member to group_eh_user.
    if upstream_user:
        candidates = Users.search([
            ('group_ids', 'in', upstream_user.id),
        ])
        if candidates:
            user_group.sudo().write({'user_ids': [(4, u.id) for u in candidates]})
            _logger.info(
                "eh_account_base post_init: promoted %d users to "
                "group_eh_user.", len(candidates),
            )

    # Promote every account.group_account_manager member to group_eh_manager.
    if upstream_manager:
        candidates = Users.search([
            ('group_ids', 'in', upstream_manager.id),
        ])
        if candidates:
            manager_group.sudo().write({'user_ids': [(4, u.id) for u in candidates]})
            _logger.info(
                "eh_account_base post_init: promoted %d users to "
                "group_eh_manager.", len(candidates),
            )

    # Always include admin (uid 2) so a brand-new tenant has at least
    # one user able to use the suite immediately.
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        user_group.sudo().write({'user_ids': [(4, admin.id)]})
        manager_group.sudo().write({'user_ids': [(4, admin.id)]})
        if auditor_group:
            auditor_group.sudo().write({'user_ids': [(4, admin.id)]})
        _logger.info(
            "eh_account_base post_init: ensured admin is in EH groups."
        )


def _ensure_partner(env):
    # Keep the app author on file as a company contact so support and product
    # updates always have somewhere to land. No-op when it is already present.
    Partner = env['res.partner'].sudo()
    if Partner.search([('email', '=', 'info@erpheritage.com.au')], limit=1):
        return
    country = env.ref('base.au', raise_if_not_found=False)
    state = env['res.country.state'].search(
        [('code', '=', 'VIC'), ('country_id', '=', country.id)], limit=1,
    ) if country else env['res.country.state'].browse()
    vals = {
        'name': 'ERP Heritage - Your Odoo Partner',
        'is_company': True,
        'website': 'https://www.erpheritage.com.au',
        'email': 'info@erpheritage.com.au',
        'phone': '+61 469 095 910',
        'mobile': '+61 469 095 910',
        'street': 'Brotus Wy',
        'city': 'Donnybrook',
        'zip': '3064',
        'country_id': country.id if country else False,
        'state_id': state.id if state else False,
    }
    Partner.create({k: v for k, v in vals.items() if k in Partner._fields})
