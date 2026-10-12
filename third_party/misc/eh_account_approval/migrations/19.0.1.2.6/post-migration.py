# -*- encoding: utf-8 -*-
"""Quarantine legacy journal-entry policies with no provable scope."""

import logging


_logger = logging.getLogger(__name__)
_NOTE = (
    "19.0.1.2.6 scope quarantine: this legacy journal-entry policy had no "
    "persisted journal/origin contract. It was disabled instead of guessing "
    "whether it should intercept payments, bank statements, reversals, or "
    "automatic entries. Select journal scope and entry origin, then reactivate."
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE eh_approval_policy AS policy
           SET active = FALSE,
               notes = CASE
                   WHEN POSITION(%s IN COALESCE(policy.notes, '')) > 0
                   THEN policy.notes
                   WHEN COALESCE(policy.notes, '') = '' THEN %s
                   ELSE policy.notes || E'\\n' || %s
               END,
               write_date = NOW()
         WHERE policy.active IS TRUE
           AND policy.document_type = 'entry'
           AND NOT EXISTS (
                SELECT 1
                  FROM eh_approval_policy_journal_rel AS scope
                 WHERE scope.policy_id = policy.id
           )
        """,
        (_NOTE, _NOTE, _NOTE),
    )
    _logger.warning(
        "Approval 19.0.1.2.6 disabled %d unscoped legacy journal-entry "
        "policy/policies; no accounting move or approval evidence was changed.",
        cr.rowcount,
    )
