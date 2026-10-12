# -*- encoding: utf-8 -*-
"""Quarantine legacy portal, send, and legal-PDF façade evidence.

Before 1.7.6 these account.move values and the attachment ``res_field``
binding were RPC-writable. No historical row shape can prove that a token,
sent flag, queued payload, or linked legal PDF came from the server workflow.
Rotate/clear those values on EH-frozen moves and detach their façade without
deleting the original attachment bytes or their account.move ownership link.
Ordinary invoices retain standard Odoo portal/delivery/legal state.
Main-attachment choices on frozen moves are also cleared: before this release a read-only
chatter/controller path could select an arbitrary ordinary attachment, so a
legacy pointer cannot be promoted as trusted evidence by shape.
"""

import logging


_logger = logging.getLogger(__name__)
_QUARANTINE_NOTE = (
    "ERP Heritage 1.7.6: detached an unverified legacy legal-PDF facade; "
    "the original bytes and account.move link are retained for audit."
)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        WITH detached AS (
            UPDATE ir_attachment attachment
               SET res_field = NULL,
                   eh_legacy_unverified_legal_pdf = TRUE,
                   description = CASE
                       WHEN POSITION(%s IN COALESCE(description, '')) > 0
                       THEN description
                       WHEN COALESCE(description, '') = ''
                       THEN %s
                       ELSE description || E'\\n' || %s
                   END
              FROM account_move move
             WHERE attachment.res_model = 'account.move'
               AND attachment.res_id IS NOT NULL
               AND attachment.res_id != 0
               AND attachment.res_field = 'invoice_pdf_report_file'
               AND move.id = attachment.res_id
               AND (
                   move.eh_sealed IS TRUE
                   OR move.eh_legacy_unverified_seal IS TRUE
               )
         RETURNING attachment.id
        ), cleared_main AS (
            UPDATE account_move move
               SET message_main_attachment_id = NULL
             WHERE move.message_main_attachment_id IS NOT NULL
               AND (
                   move.eh_sealed IS TRUE
                   OR move.eh_legacy_unverified_seal IS TRUE
               )
         RETURNING move.id
        )
        SELECT
            (SELECT COUNT(*) FROM detached),
            (SELECT COUNT(*) FROM cleared_main)
        """,
        (_QUARANTINE_NOTE, _QUARANTINE_NOTE, _QUARANTINE_NOTE),
    )
    detached_count, cleared_main_count = cr.fetchone()

    # These fields were independently client-writable only with respect to the
    # suite's stronger sealed-evidence claim. Ordinary Odoo invoices retain
    # their valid portal links, sent status, queue state, and legal PDFs; wiping
    # those records would destroy operational/legal state without improving an
    # EH seal. Field availability differs by Odoo series (sending_data is 18+),
    # so build fixed allowlisted SQL from the actual upgraded schema.
    cr.execute(
        """
        SELECT attname
          FROM pg_attribute
         WHERE attrelid = 'account_move'::regclass
           AND attnum > 0
           AND NOT attisdropped
        """
    )
    move_columns = {row[0] for row in cr.fetchall()}
    candidates = (
        ('access_token', 'NULL', 'IS NOT NULL'),
        ('is_move_sent', 'FALSE', 'IS TRUE'),
        ('sending_data', 'NULL', 'IS NOT NULL'),
        ('send_and_print_values', 'NULL', 'IS NOT NULL'),
    )
    present = [item for item in candidates if item[0] in move_columns]
    if present:
        assignments = ', '.join(
            '%s = %s' % (name, replacement)
            for name, replacement, _predicate in present
        )
        predicates = ' OR '.join(
            '%s %s' % (name, predicate)
            for name, _replacement, predicate in present
        )
        cr.execute(
            'UPDATE account_move SET %s WHERE '
            '(eh_sealed IS TRUE OR eh_legacy_unverified_seal IS TRUE) '
            'AND (%s)' % (assignments, predicates)
        )
        cleared_move_count = cr.rowcount
    else:  # pragma: no cover - account.move always has at least one today
        cleared_move_count = 0

    _logger.warning(
        "Quarantined legacy account.move delivery evidence on %s move(s); "
        "detached %s legal-PDF facade attachment(s), cleared %s unverified "
        "frozen-move main-attachment pointer(s), and preserved all attachment "
        "bytes and ownership links.",
        cleared_move_count,
        detached_count,
        cleared_main_count,
    )
