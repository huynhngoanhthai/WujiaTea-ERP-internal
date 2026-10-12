# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
# All implementation work is original. The approval state machine is a
# standard pattern from the corporate-controls literature, encoded
# afresh against the Odoo account.move post pipeline. No code or
# comments derive from any proprietary or third-party Odoo module.
#
##############################################################################
{
    'name': 'Approval Workflow',
    'summary': 'Multi-step spend authorization for vendor bills and journal entries that blocks posting until every required approver signs off. Configurable approval policies per company and document type, currency-rounded amount bands, named, group, and N-of-M approvers, atomic compare-and-set transitions, immutable audit evidence, and tested SLA escalation. Search: odoo 19 approval workflow, vendor bill approval, journal entry approval, approval matrix by amount, multi-step approval accounting, block posting until approved, approval SLA escalation, audit log approval odoo.',
    'description': """Approval Workflow is the corporate spend control most Community accounting stacks skip: a configurable approval chain that blocks account.move posting until a defined set of approvers has signed off.

Amount-band policies. One policy per company and document type, with ordered rules. Currency-rounded boundaries select the matching rule. Exact branch policies take priority and accounting-root policies provide a controlled fallback.

Multi-step ordered approvals. A step may name users, use group members, or require an N-of-M quorum across both sources. Submission seals the eligible-user snapshot and refuses an unattainable quorum. Steps run top-to-bottom in explicit sequence order, so unrelated security changes never silently reorder an in-flight chain.

Atomic step transitions. Advancing the current step uses a raw SQL UPDATE with a stale-step guard, so two concurrent approvers in the same group can never both advance the request from step N to N+1. One wins, the other gets a clean retry. This race is covered by a regression test.

Post gate. The account.move post pipeline is gated: when a matching policy applies and the request is not yet approved, posting raises with a message that names the policy, the pending group, and the step. The gate runs before upstream posting, so sequence numbering and reconciliation side effects only fire after approval, with no half-posted, gap-numbered move.

Re-approval on material change. A material amount change after full approval rolls the request back to step zero and requires every step to re-sign. The material threshold is a percentage with an optional absolute floor, configurable per policy, so a large-percentage but tiny-absolute change can be exempted. The watched edit fields are a fixed set (lines, amounts, currency, partner); edits while approval is still in progress are not gated.

Append-only audit log. Every transition (submitted, approved, rejected, withdrawn, restarted, reset, invalidated, escalated, completed) lands as an immutable row with actor, timestamp, and comment. Writes and deletion are refused at the model level.

SLA and escalation. Each rule can carry an SLA target in hours that computes a due time and an on-track, at-risk (at eighty percent of the window consumed), or breached state. An hourly cron posts chatter, queues the shipped email reminder, and performs one-shot auto-escalation to a configured group. The request-local escalation grants that group authority to sign the open step without mutating the policy snapshot. Escalation is idempotent, and each request runs inside its own database savepoint so one SQL failure cannot abort the batch.

Reject, withdraw, restart. Any approver in the pending group can reject the request (terminal). The requester or an accounting manager can withdraw the whole request. Withdrawn or rejected requests can be restarted from step zero.

No silent fallbacks. A missing policy, a missing matching rule, and an approver acting outside the pending group each raise an explicit message naming the bad config.

Activity-driven notifications. Each new step schedules a To-Do activity for every eligible active named, group, and injected approver. SLA reminders also queue the shipped email template.""",
    'author': 'ERP Heritage',
    'website': 'https://www.erpheritage.com.au/',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '19.0.1.2.8',
    'depends': ['eh_account_base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/eh_isolation_rules.xml',
        'data/sequences.xml',
        'data/cron.xml',
        'data/email_templates.xml',
        'wizards/approval_decision_wizard_views.xml',
        'views/approval_policy_views.xml',
        'views/approval_request_views.xml',
        'views/approval_log_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'data/menus.xml',
    ],
    'assets': {
        'web.assets_backend': ['eh_account_approval/static/src/js/tours/approval_tour.js'],
    },
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
