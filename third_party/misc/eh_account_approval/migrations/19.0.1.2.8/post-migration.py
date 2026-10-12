"""Align approval currency and repair known legacy reminder templates."""


_LEGACY_EMAIL_FROM = (
    "{{ (object.company_id.email or user.email) | safe }}"
)
_CURRENT_EMAIL_FROM = "{{ object.company_id.email or user.email }}"


def migrate(cr, version):
    cr.execute("""
        UPDATE eh_approval_request AS request
           SET currency_id = company.currency_id
          FROM account_move AS move
          JOIN res_company AS company ON company.id = move.company_id
         WHERE request.move_id = move.id
           AND request.currency_id IS DISTINCT FROM company.currency_id
    """)
    # ``email_templates.xml`` is noupdate data, so correcting its source does
    # not repair databases upgraded from releases which shipped Jinja's
    # ``| safe`` filter. Odoo 16 evaluates scalar template fields through
    # safe_eval and rejects that filter. Replace only exact vendor default;
    # preserve any administrator-customised sender expression.
    cr.execute(
        """
        UPDATE mail_template AS template
           SET email_from = %s,
               write_date = NOW()
          FROM ir_model_data AS data
         WHERE data.module = 'eh_account_approval'
           AND data.name = 'email_template_eh_approval_reminder'
           AND data.model = 'mail.template'
           AND data.res_id = template.id
           AND template.email_from = %s
        """,
        (_CURRENT_EMAIL_FROM, _LEGACY_EMAIL_FROM),
    )
