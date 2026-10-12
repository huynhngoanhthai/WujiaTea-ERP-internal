# -*- encoding: utf-8 -*-
"""Quarantine unverifiable live approvals and anchor valid snapshots."""

import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    requests = env['eh.approval.request'].sudo().search([
        ('state', 'in', ('in_review', 'approved')),
    ], order='id')
    quarantined = 0
    for request in requests:
        payload = request.approval_snapshot or {}
        digest = (
            request._eh_snapshot_digest(payload) if payload else False
        )
        if (
            payload.get('schema') == 'eh-approval-authorization-v2'
            and request.approval_snapshot_hash
            and digest == request.approval_snapshot_hash
        ):
            continue
        prior_state = request.state
        request.write({
            'state': 'withdrawn',
            'current_step': 0,
            'approval_cycle': (request.approval_cycle or 1) + 1,
            'approval_snapshot': False,
            'approval_snapshot_hash': False,
            'total_steps': 0,
            'submitted_at': False,
        })
        request._eh_log(
            'reset',
            "Legacy %s approval quarantined on upgrade: the exact approver "
            "authorization at submission time was not captured. Restart and "
            "submit again to create a verifiable snapshot." % prior_state,
        )
        quarantined += 1
    if quarantined:
        _logger.warning(
            "eh_account_approval 19.0.1.2.3: quarantined %d live legacy "
            "approvals without reconstructible v2 authorization/basis "
            "snapshots.",
            quarantined,
        )

    # Every current v2 snapshot also receives an append-only cycle anchor.
    # Older releases kept only the mutable "current snapshot" field, so a
    # later re-approval overwrote the authorization evidence for prior votes.
    # We cannot reconstruct already-lost cycles, but we can preserve every
    # still-verifiable snapshot before normal work resumes.
    anchored = 0
    candidates = env['eh.approval.request'].sudo().search([
        ('approval_snapshot_hash', '!=', False),
    ], order='id')
    Log = env['eh.approval.log'].sudo()
    for request in candidates:
        payload = request.approval_snapshot or {}
        digest = request.approval_snapshot_hash
        if (
            payload.get('schema') != 'eh-approval-authorization-v2'
            or request._eh_snapshot_digest(payload) != digest
            or Log.search_count([
                ('request_id', '=', request.id),
                ('authorization_snapshot_hash', '=', digest),
            ])
        ):
            continue
        Log.create({
            'request_id': request.id,
            'cycle': request.approval_cycle or 1,
            'action': 'snapshot_anchored',
            'step': request.current_step,
            'user_id': SUPERUSER_ID,
            'comment': (
                "Upgrade anchor for the verifiable current authorization "
                "snapshot; the row timestamp is the migration time, not the "
                "original submission time."
            ),
            'authorization_snapshot': payload,
            'authorization_snapshot_hash': digest,
        })
        anchored += 1
    if anchored:
        _logger.info(
            "eh_account_approval 19.0.1.2.3: anchored %d current "
            "authorization snapshots in append-only cycle logs.", anchored,
        )
