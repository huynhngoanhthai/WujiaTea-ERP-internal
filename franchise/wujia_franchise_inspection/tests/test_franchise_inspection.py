# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged('post_install', '-at_install', 'wujia_inspection')
class TestFranchiseInspection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Inspection = cls.env['wujia.franchise.inspection']
        cls.Template = cls.env['wujia.franchise.inspection.template']
        cls.Category = cls.env['wujia.franchise.inspection.category']
        cls.Question = cls.env['wujia.franchise.inspection.question']
        cls.Grade = cls.env['wujia.franchise.inspection.grade']

        # 1. Tạo Cửa hàng
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Store 01 Partner',
        })
        cls.store = cls.Franchise.create({
            'code': 'TEST-STORE-01',
            'name': 'Test Store 01',
            'partner_id': cls.partner.id,
            'status': 'active',
        })

        # 2. Tạo Thang điểm Xếp loại A, B, C, D nếu chưa có
        cls.grade_a = cls.Grade.search([('name', '=', 'A')], limit=1)
        if not cls.grade_a:
            cls.grade_a = cls.Grade.create({'name': 'A', 'min_score': 90.0, 'max_score': 100.0, 'color': '#28a745'})
        cls.grade_b = cls.Grade.search([('name', '=', 'B')], limit=1)
        if not cls.grade_b:
            cls.grade_b = cls.Grade.create({'name': 'B', 'min_score': 75.0, 'max_score': 89.9, 'color': '#17a2b8'})
        cls.grade_c = cls.Grade.search([('name', '=', 'C')], limit=1)
        if not cls.grade_c:
            cls.grade_c = cls.Grade.create({'name': 'C', 'min_score': 60.0, 'max_score': 74.9, 'color': '#ffc107'})
        cls.grade_d = cls.Grade.search([('name', '=', 'D')], limit=1)
        if not cls.grade_d:
            cls.grade_d = cls.Grade.create({'name': 'D', 'min_score': 0.0, 'max_score': 59.9, 'color': '#dc3545'})

        # 3. Tạo Danh mục & Mẫu khảo sát
        cls.category = cls.Category.create({
            'name': 'Vệ sinh & An toàn',
            'code': 'VSAT',
            'sequence': 10,
        })

        cls.template = cls.Template.create({
            'name': 'Mẫu kiểm tra vệ sinh chuẩn',
            'code': 'TPL-TEST-01',
            'line_ids': [
                (0, 0, {
                    'category_id': cls.category.id,
                    'name': 'Khu vực quầy pha chế sạch sẽ',
                    'max_score': 50.0,
                    'sequence': 10,
                }),
                (0, 0, {
                    'category_id': cls.category.id,
                    'name': 'Nguyên vật liệu có tem nhãn hạn sử dụng',
                    'max_score': 50.0,
                    'sequence': 20,
                }),
            ]
        })

    def test_01_create_inspection_from_template(self):
        """Kiểm tra tạo phiếu khảo sát từ mẫu và tự sinh các dòng tiêu chí."""
        inspection = self.Inspection.create({
            'franchise_id': self.store.id,
            'template_id': self.template.id,
            'planned_date': fields.Date.today(),
        })
        inspection._onchange_template_id()

        self.assertEqual(inspection.state, 'draft')
        self.assertEqual(len(inspection.line_ids), 2, "Phiếu khảo sát phải nạp đủ 2 dòng tiêu chí từ mẫu.")
        self.assertEqual(inspection.max_checklist_score, 100.0, "Tổng điểm tối đa của checklist phải bằng 100.")

    def test_02_scoring_and_grading_grade_a(self):
        """Kiểm tra chấm điểm đạt điểm tối đa và tự động xếp loại A."""
        inspection = self.Inspection.create({
            'franchise_id': self.store.id,
            'template_id': self.template.id,
            'planned_date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 1',
                    'max_score': 50.0,
                    'is_passed': True,
                    'score': 50.0,
                }),
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 2',
                    'max_score': 50.0,
                    'is_passed': True,
                    'score': 50.0,
                }),
            ]
        })
        inspection._compute_total_score()
        self.assertEqual(inspection.total_score, 100.0)
        self.assertEqual(inspection.grade_id.name, 'A', "Đạt 100 điểm phải xếp loại A.")

    def test_03_scoring_grade_c_and_remediation_workflow(self):
        """Kiểm tra khi có tiêu chí không đạt, hệ thống xếp loại C/D và chuyển trạng thái cần khắc phục."""
        inspection = self.Inspection.create({
            'franchise_id': self.store.id,
            'template_id': self.template.id,
            'planned_date': fields.Date.today(),
            'state': 'in_progress',
            'line_ids': [
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 1 đạt',
                    'max_score': 50.0,
                    'is_passed': True,
                    'score': 50.0,
                }),
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 2 không đạt',
                    'max_score': 50.0,
                    'is_passed': False,
                    'score': 20.0,
                    'note': 'Hạn sử dụng bị mờ',
                }),
            ]
        })
        inspection._compute_total_score()
        self.assertEqual(inspection.total_score, 70.0)
        self.assertEqual(inspection.grade_id.name, 'C', "Đạt 70 điểm phải xếp loại C.")

    def test_04_store_latest_inspection_computation(self):
        """Kiểm tra cập nhật thông tin khảo sát gần nhất trên hồ sơ cửa hàng."""
        insp = self.Inspection.create({
            'franchise_id': self.store.id,
            'template_id': self.template.id,
            'planned_date': fields.Date.today(),
            'state': 'done',
            'line_ids': [
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 1',
                    'max_score': 50.0,
                    'is_passed': True,
                    'score': 45.0,
                }),
                (0, 0, {
                    'category_id': self.category.id,
                    'name': 'Tiêu chí 2',
                    'max_score': 50.0,
                    'is_passed': True,
                    'score': 45.0,
                }),
            ]
        })
        insp._compute_total_score()
        self.store._compute_latest_inspection_info()

        self.assertEqual(self.store.latest_inspection_id.id, insp.id)
        self.assertEqual(self.store.latest_total_score, 90.0)
        self.assertEqual(self.store.latest_grade_id.name, 'A')
