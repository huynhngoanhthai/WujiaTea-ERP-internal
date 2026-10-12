# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Invalidate cached payloads when non-ledger report inputs change."""

from odoo import _, api, models
from odoo.exceptions import AccessError

from .account_move import (
    _EH_COMMERCIAL_PROJECTION_REFRESH,
    _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY,
)


_EH_PARTNER_ENGINE = 'eh_partner_projection_internal'
_EH_PARTNER_ENGINE_CAPABILITY = object()
_EH_SERVER_OWNED_PARTNER_FIELDS = frozenset({
    'commercial_partner_id',
    'commercial_company_name',
})
# Odoo 18+ updates accounting-line partner roots inside res.partner.write.
# Generated 16/17 targets flip this marker and supply the same cascade here.
_EH_CORE_REPARENT_REFRESHES_MOVE_LINES = True


def _bump_all_companies(env):
    env['res.company'].sudo()._eh_bump_global_report_version()


def _bump_companies(env, company_ids):
    ids = {int(company_id) for company_id in company_ids if company_id}
    if ids:
        env['res.company'].sudo()._eh_bump_move_version(ids)
    else:
        _bump_all_companies(env)


def _bump_company_subtrees(env, company_ids):
    owner_ids = {int(company_id) for company_id in company_ids if company_id}
    if not owner_ids:
        return
    descendants = env['res.company'].sudo().with_context(
        active_test=False,
    ).search([
        ('id', 'child_of', tuple(sorted(owner_ids))),
    ])
    _bump_companies(env, descendants.ids)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def default_get(self, fields_list):
        """Never source commercial projections from context/ir.default."""
        defaults = super().default_get(fields_list)
        if not (
            self.env.context.get(_EH_PARTNER_ENGINE)
            is _EH_PARTNER_ENGINE_CAPABILITY
        ):
            for field_name in (
                _EH_SERVER_OWNED_PARTNER_FIELDS.intersection(fields_list)
            ):
                defaults.pop(field_name, None)
        return defaults

    @api.model
    def _eh_guard_server_owned_commercial_values(self, vals):
        protected = _EH_SERVER_OWNED_PARTNER_FIELDS.intersection(vals)
        if not protected:
            return
        if (
            self.env.context.get(_EH_PARTNER_ENGINE)
            is _EH_PARTNER_ENGINE_CAPABILITY
        ):
            return
        raise AccessError(_(
            "Commercial-partner projections are server-owned and cannot be "
            "supplied or edited directly: %(fields)s",
            fields=', '.join(sorted(protected)),
        ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._eh_guard_server_owned_commercial_values(vals)
        protected_defaults = {
            'default_%s' % field_name
            for field_name in _EH_SERVER_OWNED_PARTNER_FIELDS
        }
        create_context = {
            key: value for key, value in self.env.context.items()
            if key not in protected_defaults
        }
        create_self = self.with_context(create_context)
        return super(ResPartner, create_self).create(vals_list)

    def write(self, vals):
        self._eh_guard_server_owned_commercial_values(vals)
        hierarchy_change = bool({'parent_id', 'is_company'}.intersection(vals))
        affected_moves = self.env['account.move']
        legacy_reparent_lines = []
        if (
            'parent_id' in vals
            and not _EH_CORE_REPARENT_REFRESHES_MOVE_LINES
        ):
            MoveLine = self.env['account.move.line'].sudo()
            legacy_reparent_lines = [
                (partner, MoveLine.search([('partner_id', '=', partner.id)]))
                for partner in self
            ]
        if hierarchy_change and self:
            affected_partner_ids = self.sudo().with_context(
                active_test=False,
            ).search([
                ('id', 'child_of', self.ids),
            ]).ids
            affected_moves = self.env['account.move'].sudo().search([
                ('partner_id', 'in', affected_partner_ids),
            ])
        write_self = self
        if 'parent_id' in vals:
            # Odoo 18/19 refresh account.move.line partners and stored move
            # commercial roots from inside res.partner.write().  Grant only
            # that server-owned cascade; object capabilities cannot arrive
            # through RPC context.  AccountMove then discards core's generic
            # scalar and recomputes the installed MRO value (including the
            # hr_expense own-account rule).
            write_self = self.with_context(**{
                _EH_PARTNER_ENGINE: _EH_PARTNER_ENGINE_CAPABILITY,
                _EH_COMMERCIAL_PROJECTION_REFRESH:
                    _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY,
            })
        result = super(ResPartner, write_self).write(vals)
        for partner, move_lines in legacy_reparent_lines:
            partner.invalidate_recordset(['commercial_partner_id'])
            # Match the 18+ core cascade without an accounting-engine bypass:
            # Base's sealed-line guard must still reject historical rewrites.
            move_lines.write({
                'partner_id': partner.commercial_partner_id.id,
            })
        if affected_moves:
            affected_moves.with_context(**{
                _EH_COMMERCIAL_PROJECTION_REFRESH:
                    _EH_COMMERCIAL_PROJECTION_REFRESH_CAPABILITY,
            })._eh_refresh_commercial_projection()
        if {'name', 'parent_id', 'is_company', 'company_name',
                'commercial_company_name', 'active'}.intersection(vals):
            _bump_all_companies(self.env)
        return result

    def unlink(self):
        invalidate = bool(self)
        result = super().unlink()
        if invalidate:
            _bump_all_companies(self.env)
        return result


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'name', 'code', 'type', 'company_id', 'active'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        if company_ids:
            _bump_companies(self.env, company_ids)
        return result


class AccountGroup(models.Model):
    _inherit = 'account.group'

    @api.model_create_multi
    def create(self, vals_list):
        groups = super().create(vals_list)
        _bump_company_subtrees(
            groups.env, groups.mapped('company_id.id'),
        )
        return groups

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'name', 'parent_id', 'code_prefix_start',
                'code_prefix_end'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_company_subtrees(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        _bump_company_subtrees(self.env, company_ids)
        return result


class AccountAccountTag(models.Model):
    _inherit = 'account.account.tag'

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'applicability', 'active'}.intersection(vals):
            _bump_all_companies(self.env)
        return result

    def unlink(self):
        invalidate = bool(self)
        result = super().unlink()
        if invalidate:
            _bump_all_companies(self.env)
        return result


class AccountTaxRepartitionLine(models.Model):
    _inherit = 'account.tax.repartition.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        _bump_companies(lines.env, lines.mapped('company_id.id'))
        return lines

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'account_id', 'tax_id', 'factor_percent',
                'repartition_type'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        _bump_companies(self.env, company_ids)
        return result


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'name', 'code', 'plan_id', 'company_id',
                'active'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        _bump_companies(self.env, company_ids)
        return result


class AccountAnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    def write(self, vals):
        result = super().write(vals)
        if {'name', 'parent_id', 'root_id', 'active'}.intersection(vals):
            _bump_all_companies(self.env)
        return result

    def unlink(self):
        invalidate = bool(self)
        result = super().unlink()
        if invalidate:
            _bump_all_companies(self.env)
        return result


class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    @api.model_create_multi
    def create(self, vals_list):
        statements = super().create(vals_list)
        _bump_companies(statements.env, statements.mapped('company_id.id'))
        return statements

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'name', 'reference', 'date', 'balance_start', 'balance_end_real',
                'journal_id'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        _bump_companies(self.env, company_ids)
        return result


class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        _bump_companies(lines.env, lines.mapped('company_id.id'))
        return lines

    def write(self, vals):
        company_ids = set(self.mapped('company_id.id'))
        result = super().write(vals)
        if {'statement_id', 'sequence', 'partner_id', 'partner_name',
                'payment_ref', 'amount', 'amount_currency', 'journal_id',
                'company_id', 'date'}.intersection(vals):
            company_ids.update(self.mapped('company_id.id'))
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('company_id.id'))
        result = super().unlink()
        _bump_companies(self.env, company_ids)
        return result


class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        _bump_companies(lines.env, lines.mapped('journal_id.company_id').ids)
        return lines

    def write(self, vals):
        company_ids = set(self.mapped('journal_id.company_id').ids)
        result = super().write(vals)
        if {'payment_account_id', 'journal_id',
                'payment_method_id'}.intersection(vals):
            company_ids.update(self.mapped('journal_id.company_id').ids)
            _bump_companies(self.env, company_ids)
        return result

    def unlink(self):
        company_ids = set(self.mapped('journal_id.company_id').ids)
        result = super().unlink()
        _bump_companies(self.env, company_ids)
        return result
