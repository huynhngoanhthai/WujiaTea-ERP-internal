# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    employee_assignment_ids = fields.One2many(
        'wujia.franchise.employee.assignment',
        'franchise_id',
        string='Employee Assignments',
    )
    employee_count = fields.Integer(
        string='Employee Count',
        compute='_compute_operation_counts',
    )
    work_schedule_count = fields.Integer(
        string='Schedule Count',
        compute='_compute_operation_counts',
    )
    operation_expense_count = fields.Integer(
        string='Expense Count',
        compute='_compute_operation_counts',
    )
    operation_revenue_count = fields.Integer(
        string='Revenue Count',
        compute='_compute_operation_counts',
    )

    def _compute_operation_counts(self):
        """Batch-compute operation counts using _read_group() to avoid N+1 queries.

        Uses 4 _read_group() calls total (one per related model), regardless of
        how many store records are in self. This is the Odoo 19 standard API
        (read_group() was deprecated in 19.0). Results are aggregated into dicts
        keyed by franchise_id for O(1) lookup per record.

        Anti-N+1 compliance: Zero DB queries inside the for loop (R14).
        """
        ids = self.ids
        if not ids:
            for store in self:
                store.employee_count = 0
                store.work_schedule_count = 0
                store.operation_expense_count = 0
                store.operation_revenue_count = 0
            return

        # --- Batch 1: Active employee assignments (state='working') ---
        Assignment = self.env['wujia.franchise.employee.assignment']
        assignment_groups = Assignment._read_group(
            domain=[('franchise_id', 'in', ids), ('state', '=', 'working')],
            groupby=['franchise_id'],
            aggregates=['__count'],
        )
        assignment_map = {franchise.id: count for franchise, count in assignment_groups}

        # --- Batch 2: Work schedules ---
        Schedule = self.env['wujia.franchise.work.schedule']
        schedule_groups = Schedule._read_group(
            domain=[('franchise_id', 'in', ids)],
            groupby=['franchise_id'],
            aggregates=['__count'],
        )
        schedule_map = {franchise.id: count for franchise, count in schedule_groups}

        # --- Batch 3: Operating expenses ---
        Expense = self.env['wujia.franchise.expense']
        expense_groups = Expense._read_group(
            domain=[('franchise_id', 'in', ids)],
            groupby=['franchise_id'],
            aggregates=['__count'],
        )
        expense_map = {franchise.id: count for franchise, count in expense_groups}

        # --- Batch 4: Revenue records ---
        Revenue = self.env['wujia.franchise.revenue']
        revenue_groups = Revenue._read_group(
            domain=[('franchise_id', 'in', ids)],
            groupby=['franchise_id'],
            aggregates=['__count'],
        )
        revenue_map = {franchise.id: count for franchise, count in revenue_groups}

        # --- Assign results (single loop, dict lookup only — no DB queries) ---
        for store in self:
            store.employee_count = assignment_map.get(store.id, 0)
            store.work_schedule_count = schedule_map.get(store.id, 0)
            store.operation_expense_count = expense_map.get(store.id, 0)
            store.operation_revenue_count = revenue_map.get(store.id, 0)

    def action_view_store_employees(self):
        self.ensure_one()
        action = self.env.ref('wujia_franchise_operations.action_wujia_franchise_employee_assignment').read()[0]
        action['domain'] = [('franchise_id', '=', self.id)]
        action['context'] = {'default_franchise_id': self.id}
        return action

    def action_view_store_schedules(self):
        self.ensure_one()
        action = self.env.ref('wujia_franchise_operations.action_wujia_franchise_work_schedule').read()[0]
        action['domain'] = [('franchise_id', '=', self.id)]
        action['context'] = {'default_franchise_id': self.id}
        return action

    def action_view_store_expenses(self):
        self.ensure_one()
        action = self.env.ref('wujia_franchise_operations.action_wujia_franchise_expense').read()[0]
        action['domain'] = [('franchise_id', '=', self.id)]
        action['context'] = {'default_franchise_id': self.id}
        return action

    def action_view_store_revenues(self):
        self.ensure_one()
        action = self.env.ref('wujia_franchise_operations.action_wujia_franchise_revenue').read()[0]
        action['domain'] = [('franchise_id', '=', self.id)]
        action['context'] = {'default_franchise_id': self.id}
        return action
