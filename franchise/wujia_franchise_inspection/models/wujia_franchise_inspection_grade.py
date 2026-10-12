# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
# pyrefly: ignore [missing-import]
from odoo.exceptions import ValidationError


class WujiaFranchiseInspectionGrade(models.Model):
    _name = 'wujia.franchise.inspection.grade'
    _description = 'Inspection Grade Configuration'
    _order = 'min_score desc'

    name = fields.Char(
        string='Grade',
        required=True,
        help='Grade name, e.g.: A, B, C, D',
    )
    min_score = fields.Float(
        string='Minimum Score',
        required=True,
        help='Minimum score to achieve this grade (inclusive)',
    )
    max_score = fields.Float(
        string='Maximum Score',
        required=True,
        default=100.0,
        help='Maximum score for this grade (inclusive)',
    )
    description = fields.Text(
        string='Description',
        help='Short description for this grade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    color = fields.Integer(
        string='Color',
        help='Badge color index',
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Grade name must be unique!'),
        ('score_check', 'CHECK(min_score <= max_score)',
         'Minimum score must be less than or equal to maximum score!'),
    ]


    @api.model
    def _init_default_grades(self):
        """Tạo các xếp hạng mặc định (A, B, C, D) nếu chưa tồn tại trong database."""
        default_grades = [
            {'name': 'A', 'min_score': 96.0, 'max_score': 100.0, 'sequence': 1, 'color': 10, 'description': 'Excellent'},
            {'name': 'B', 'min_score': 83.0, 'max_score': 95.99, 'sequence': 2, 'color': 2, 'description': 'Good'},
            {'name': 'C', 'min_score': 70.0, 'max_score': 82.99, 'sequence': 3, 'color': 3, 'description': 'Average'},
            {'name': 'D', 'min_score': 0.0, 'max_score': 69.99, 'sequence': 4, 'color': 1, 'description': 'Poor'},
        ]
        for grade_data in default_grades:
            existing = self.with_context(active_test=False).search([('name', '=', grade_data['name'])], limit=1)
            if not existing:
                self.create(grade_data)


    @api.constrains('name')
    def _check_name_unique(self):
        """Đảm bảo tên xếp hạng là duy nhất."""
        if self.env.context.get('install_mode') or self.env.context.get('import_file'):
            return
        for record in self:
            rec_id = record._origin.id if record._origin else (record.id if isinstance(record.id, int) else False)
            domain = [('name', '=', record.name)]
            if rec_id:
                domain.append(('id', '!=', rec_id))
            if self.search_count(domain) > 0:
                raise ValidationError(_('Grade "%s" already exists!', record.name))

    @api.constrains('min_score', 'max_score')
    def _check_score_overlap(self):
        """Kiểm tra các khoảng điểm không được chồng lấn nhau."""
        if self.env.context.get('install_mode') or self.env.context.get('import_file'):
            return
        for record in self:
            rec_id = record._origin.id if record._origin else (record.id if isinstance(record.id, int) else False)
            domain = [
                ('active', '=', True),
                ('min_score', '<=', record.max_score),
                ('max_score', '>=', record.min_score),
            ]
            if rec_id:
                domain.append(('id', '!=', rec_id))
            overlapping = self.search(domain, limit=1)
            if overlapping and overlapping.id != rec_id:
                raise ValidationError(
                    _('Score range [%(min)s - %(max)s] of grade "%(name)s" overlaps '
                      'with grade "%(other)s" [%(other_min)s - %(other_max)s]!',
                      min=record.min_score,
                      max=record.max_score,
                      name=record.name,
                      other=overlapping.name,
                      other_min=overlapping.min_score,
                      other_max=overlapping.max_score,
                      )
                )
