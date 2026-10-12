# -*- encoding: utf-8 -*-
"""Quarantine every seal created before durable server provenance.

Legacy ``eh_sealed`` was writable over ORM/RPC. Its value therefore cannot
prove that a suite workflow created or validated the journal entry. Preserve
the freeze and the row, but deliberately clear the trusted bit so downstream
source validators fail closed.
"""

import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE account_move
           SET eh_legacy_unverified_seal = TRUE,
               eh_sealed = FALSE
         WHERE eh_sealed = TRUE
    """)
    _logger.warning(
        "Quarantined %s legacy account.move seal(s) as unverified; no "
        "journal entry was deleted or promoted.",
        cr.rowcount,
    )
