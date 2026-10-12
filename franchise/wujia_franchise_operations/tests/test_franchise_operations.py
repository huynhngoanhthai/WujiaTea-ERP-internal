# -*- coding: utf-8 -*-
from datetime import date, timedelta
from odoo import tools
from odoo.fields import Date
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wujia_franchise_operations')
class TestFranchiseOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Employee = cls.env['wujia.franchise.employee']
        cls.Assignment = cls.env['wujia.franchise.employee.assignment']
        cls.ShiftTemplate = cls.env['wujia.franchise.shift.template']
        cls.Schedule = cls.env['wujia.franchise.work.schedule']
        cls.ExpenseCategory = cls.env['wujia.franchise.expense.category']
        cls.Expense = cls.env['wujia.franchise.expense']
        cls.Revenue = cls.env['wujia.franchise.revenue']

        cls.partner1 = cls.Partner.create({'name': 'Store Partner 1', 'is_franchise': True})
        cls.partner2 = cls.Partner.create({'name': 'Store Partner 2', 'is_franchise': True})

        cls.store1 = cls.Franchise.create({
            'code': 'HCM-OPS-01',
            'name': 'Wujia Store 1',
            'partner_id': cls.partner1.id,
        })
        cls.store2 = cls.Franchise.create({
            'code': 'HCM-OPS-02',
            'name': 'Wujia Store 2',
            'partner_id': cls.partner2.id,
        })

        cls.employee = cls.Employee.create({
            'name': 'Nguyen Van A',
            'phone': '0901234567',
        })

        cls.shift_morning = cls.ShiftTemplate.create({
            'name': 'Test Morning Shift',
            'code': 'TEST_MORNING',
            'start_time': 6.5,
            'end_time': 14.5,
            'break_minutes': 30,
        })

        cls.expense_cat = cls.ExpenseCategory.create({
            'name': 'Electricity Bill',
            'code': 'TEST_ELEC',
            'expense_type': 'operating',
        })

    def test_01_primary_assignment_unique_constraint(self):
        """Test AC4: Max 1 active primary assignment per employee."""
        assign1 = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'is_primary': True,
            'state': 'working',
        })
        self.assertTrue(assign1.is_primary)

        with self.assertRaises(ValidationError):
            self.Assignment.create({
                'employee_id': self.employee.id,
                'franchise_id': self.store2.id,
                'is_primary': True,
                'state': 'working',
            })

    def test_02_assignment_date_range_overlap(self):
        """Test AC3: Overlapping assignments at the same store trigger ValidationError."""
        self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'date_from': date(2026, 1, 1),
            'date_to': date(2026, 6, 30),
            'state': 'working',
        })

        with self.assertRaises(ValidationError):
            self.Assignment.create({
                'employee_id': self.employee.id,
                'franchise_id': self.store1.id,
                'date_from': date(2026, 5, 1),
                'date_to': date(2026, 8, 31),
                'state': 'working',
            })

    def test_03_shift_template_hours_computation(self):
        """Test shift planned hours computation (normal vs overnight)."""
        self.assertAlmostEqual(self.shift_morning.planned_hours, 7.5)

        overnight = self.ShiftTemplate.create({
            'name': 'Overnight Shift',
            'code': 'TEST_NIGHT',
            'start_time': 22.0,
            'end_time': 6.0,
            'break_minutes': 60,
        })
        self.assertAlmostEqual(overnight.planned_hours, 7.0)

    def test_04_work_schedule_overlap_and_confirm(self):
        """Test AC6 & AC7: Schedule overlap prevention and confirmation workflow."""
        assign = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'state': 'working',
        })

        sched1 = self.Schedule.create({
            'franchise_id': self.store1.id,
            'assignment_id': assign.id,
            'work_date': date(2026, 9, 15),
            'shift_template_id': self.shift_morning.id,
        })
        sched1._onchange_calculate_planned_times()
        sched1.action_confirm()
        self.assertEqual(sched1.state, 'confirmed')

        sched2 = self.Schedule.new({
            'franchise_id': self.store1.id,
            'assignment_id': assign.id,
            'work_date': date(2026, 9, 15),
            'shift_template_id': self.shift_morning.id,
        })
        sched2._onchange_calculate_planned_times()

        with self.assertRaises(ValidationError):
            sched2_real = self.Schedule.create({
                'franchise_id': self.store1.id,
                'assignment_id': assign.id,
                'work_date': date(2026, 9, 15),
                'shift_template_id': self.shift_morning.id,
                'planned_start': sched1.planned_start,
                'planned_end': sched1.planned_end,
                'planned_hours': sched1.planned_hours,
            })
            sched2_real._check_overlapping_schedules()

    def test_05_expense_creation_and_confirm(self):
        """Test AC8: Expense creation, positive amount constraint, and confirmation."""
        expense = self.Expense.create({
            'franchise_id': self.store1.id,
            'category_id': self.expense_cat.id,
            'amount': 500000.0,
            'description': 'Electricity bill for September 2026',
        })
        self.assertEqual(expense.state, 'draft')
        expense.action_confirm()
        self.assertEqual(expense.state, 'confirmed')
        self.assertTrue(expense.confirmed_by_id)

        with self.assertRaises(ValidationError):
            self.Expense.create({
                'franchise_id': self.store1.id,
                'category_id': self.expense_cat.id,
                'amount': -100.0,
                'description': 'Negative amount expense',
            })

    def test_06_revenue_idempotency_and_zero_amount(self):
        """Test AC9 & AC10: Idempotent daily revenue constraint and zero amount revenue declaration."""
        rev1 = self.Revenue.create({
            'franchise_id': self.store1.id,
            'business_date': date(2026, 9, 11),
            'amount': 15000000.0,
        })
        rev1.action_confirm()
        self.assertEqual(rev1.state, 'confirmed')

        # Duplicate business date at same store triggers ValidationError
        with self.assertRaises(ValidationError):
            self.Revenue.create({
                'franchise_id': self.store1.id,
                'business_date': date(2026, 9, 11),
                'amount': 20000000.0,
            })

        # Zero revenue declaration for stormy/closed day is valid
        rev_zero = self.Revenue.create({
            'franchise_id': self.store2.id,
            'business_date': date(2026, 9, 11),
            'amount': 0.0,
            'note': 'Closed due to typhoon',
        })
        self.assertEqual(rev_zero.amount, 0.0)
        rev_zero.action_confirm()
        self.assertEqual(rev_zero.state, 'confirmed')

    def test_10_revenue_import_wizard(self):
        """Test AC12: Import daily revenue via CSV/Excel wizard with auto source detection."""
        import base64
        csv_data = "Store Code,Business Date,Amount,Note\nHCM-OPS-01,2026-09-25,5000000,Test CSV Import Row 1\nHCM-OPS-02,2026-09-25,6000000,Test CSV Import Row 2\n"
        encoded = base64.b64encode(csv_data.encode('utf-8'))

        wizard = self.env['wujia.franchise.revenue.import.wizard'].create({
            'data_file': encoded,
            'file_name': 'test_revenue_data.csv',
            'default_franchise_id': self.store1.id,
        })
        action = wizard.action_import()
        self.assertEqual(action.get('type'), 'ir.actions.client')

        imported = self.Revenue.search([('source_reference', '=', 'test_revenue_data.csv')])
        self.assertEqual(len(imported), 2)
        self.assertTrue(all(r.source == 'csv' for r in imported))

    def test_11_revenue_manual_vs_import_constraints(self):
        """Test that manual revenue allows no file, but import revenue requires file."""
        import base64
        # Manual without file: should succeed
        manual_rev = self.Revenue.create({
            'franchise_id': self.store1.id,
            'business_date': date(2026, 9, 26),
            'amount': 3500000.0,
            'source': 'manual',
        })
        self.assertEqual(manual_rev.state, 'draft')
        self.assertFalse(manual_rev.import_file)

        # Import without file: should raise ValidationError
        with self.assertRaises(ValidationError):
            self.Revenue.create({
                'franchise_id': self.store2.id,
                'business_date': date(2026, 9, 26),
                'amount': 4000000.0,
                'source': 'import',
                'import_file': False,
            })

        # Import with file: should succeed
        csv_data = "Item,Qty,Price,Total\nMilk Tea,10,30000,300000\nFruit Tea,20,35000,700000\n"
        encoded = base64.b64encode(csv_data.encode('utf-8'))
        import_rev = self.Revenue.create({
            'franchise_id': self.store2.id,
            'business_date': date(2026, 9, 26),
            'amount': 1000000.0,
            'source': 'import',
            'import_file': encoded,
            'import_file_name': 'pos_orders.csv',
        })
        self.assertEqual(import_rev.state, 'draft')
        self.assertTrue(bool(import_rev.import_file))

    def test_12_revenue_compute_wizard_sum(self):
        """Test optional wizard auto calculation and column sum from uploaded file."""
        import base64
        csv_data = "Order,Date,Revenue,Notes\nORD01,2026-09-27,1500000,Table 1\nORD02,2026-09-27,2500000,Table 2\nORD03,2026-09-27,1000000,Delivery\n"
        encoded = base64.b64encode(csv_data.encode('utf-8'))

        rev = self.Revenue.create({
            'franchise_id': self.store1.id,
            'business_date': date(2026, 9, 27),
            'source': 'import',
            'import_file': encoded,
            'import_file_name': 'daily_sales.csv',
        })

        # Create wizard linked to rev
        wizard = self.env['wujia.franchise.revenue.compute.wizard'].with_context(
            default_revenue_id=rev.id
        ).create({
            'revenue_id': rev.id,
            'column_index': '2', # 3rd column: Revenue
            'has_header': True,
        })

        # Check calculated sum (1500000 + 2500000 + 1000000 = 5000000)
        self.assertEqual(wizard.row_count, 3)
        self.assertEqual(wizard.calculated_sum, 5000000.0)

        # Apply sum
        wizard.action_apply_sum()
        self.assertEqual(rev.amount, 5000000.0)


    def test_07_store_master_smart_button_counts(self):
        """Test Store Master smart buttons count computation."""
        assign = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'state': 'working',
        })
        sched = self.Schedule.create({
            'franchise_id': self.store1.id,
            'assignment_id': assign.id,
            'work_date': date(2026, 9, 20),
            'shift_template_id': self.shift_morning.id,
            'planned_start': Date.context_today(self),
            'planned_end': Date.context_today(self),
            'planned_hours': 8.0,
        })
        exp = self.Expense.create({
            'franchise_id': self.store1.id,
            'category_id': self.expense_cat.id,
            'amount': 250000.0,
            'description': 'Store maintenance',
        })
        rev = self.Revenue.create({
            'franchise_id': self.store1.id,
            'business_date': date(2026, 9, 20),
            'amount': 12000000.0,
        })

        self.store1._compute_operation_counts()
        self.assertEqual(self.store1.employee_count, 1)
        self.assertEqual(self.store1.work_schedule_count, 1)
        self.assertEqual(self.store1.operation_expense_count, 1)
        self.assertEqual(self.store1.operation_revenue_count, 1)

    def test_08_assignment_auto_compute_state_by_date(self):
        """Test auto computation of assignment state based on start and end dates."""
        today = Date.context_today(self)

        # Future start date -> scheduled
        future_assign = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'date_from': today + timedelta(days=5),
        })
        self.assertEqual(future_assign.state, 'scheduled')

        # Past start date with no end date -> working
        active_assign = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store2.id,
            'date_from': today - timedelta(days=5),
        })
        self.assertEqual(active_assign.state, 'working')

        # Past end date -> ended
        ended_assign = self.Assignment.create({
            'employee_id': self.employee.id,
            'franchise_id': self.store1.id,
            'date_from': today - timedelta(days=30),
            'date_to': today - timedelta(days=1),
        })
        self.assertEqual(ended_assign.state, 'ended')

    def test_09_action_get_work_schedules_defaults(self):
        """Test action_get_work_schedules returns smallest ID store and this week filter context."""
        action = self.Schedule.action_get_work_schedules()
        self.assertIn('context', action)
        self.assertEqual(action['context'].get('search_default_filter_this_week'), 1)
        smallest_store = self.env['wujia.franchise.management'].search([('active', '=', True)], order='id asc', limit=1)
        self.assertEqual(action['context'].get('search_default_franchise_id'), smallest_store.id)

    def test_13_composite_indexes_exist(self):
        """Test that all 5 PostgreSQL composite indexes are created and exist in database."""
        indexes_to_check = [
            'idx_wujia_revenue_store_date_state',
            'idx_work_schedule_store_date_state',
            'idx_work_schedule_emp_date',
            'idx_franchise_expense_store_cat_date',
            'idx_emp_assignment_emp_store_primary',
        ]
        for idx_name in indexes_to_check:
            self.assertTrue(
                tools.index_exists(self.env.cr, idx_name),
                f"Composite index '{idx_name}' was not created in PostgreSQL database.",
            )

