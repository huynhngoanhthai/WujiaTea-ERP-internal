# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models, _


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    supervision_user_id = fields.Many2one(
        'res.users',
        string='Assigned Supervisor',
        domain="[('share', '=', False)]",
        tracking=True,
        help='Dedicated inspection staff assigned to this store. If unset, Area Manager is responsible.'
    )
    area_manager_user_id = fields.Many2one(
        'res.users',
        string='Area Manager',
        related='area_id.manager_user_id',
        store=True,
        readonly=True
    )
    effective_supervision_user_id = fields.Many2one(
        'res.users',
        string='Effective Supervisor',
        compute='_compute_effective_supervision_user_id',
        store=True,
        index=True
    )
    nearest_supervision_schedule_date = fields.Date(
        string='Nearest Inspection Date',
        compute='_compute_nearest_schedule_date',
        store=False,
        help='Nearest upcoming inspection date (>= today), excluding past and cancelled schedules.'
    )
    inspection_ids = fields.One2many(
        'wujia.franchise.inspection',
        'franchise_id',
        string='Inspections'
    )
    inspection_count = fields.Integer(
        string='Inspection Count',
        compute='_compute_inspection_count'
    )
    inspection_chart_data = fields.Text(
        string='Inspection Chart Data',
        compute='_compute_inspection_chart_data'
    )
    latest_inspection_id = fields.Many2one(
        'wujia.franchise.inspection',
        string='Latest Inspection',
        compute='_compute_latest_inspection_info',
        store=True
    )
    latest_total_score = fields.Float(
        string='Latest Inspection Score',
        compute='_compute_latest_inspection_info',
        store=True
    )
    latest_grade_id = fields.Many2one(
        'wujia.franchise.inspection.grade',
        string='Latest Inspection Grade',
        compute='_compute_latest_inspection_info',
        store=True
    )
    latest_inspection_date = fields.Date(
        string='Latest Inspection Date',
        compute='_compute_latest_inspection_info',
        store=True
    )
    consecutive_c_count = fields.Integer(
        string='Consecutive Grade C Count',
        compute='_compute_latest_inspection_info',
        store=True,
        help='Number of consecutive completed inspections with grade C from the latest round.'
    )
    consecutive_d_count = fields.Integer(
        string='Consecutive Grade D Count',
        compute='_compute_latest_inspection_info',
        store=True,
        help='Number of consecutive completed inspections with grade D from the latest round.'
    )

    @api.depends('supervision_user_id', 'area_id.manager_user_id')
    def _compute_effective_supervision_user_id(self):
        for rec in self:
            rec.effective_supervision_user_id = rec.supervision_user_id or rec.area_id.manager_user_id or False

    def _compute_nearest_schedule_date(self):
        today = fields.Date.context_today(self)
        for rec in self:
            sched = self.env['wujia.supervision.schedule'].search([
                ('store_id', '=', rec.id),
                ('date', '>=', today),
                ('state', '!=', 'cancelled')
            ], order='date asc', limit=1)
            rec.nearest_supervision_schedule_date = sched.date if sched else False

    @api.depends('inspection_ids')
    def _compute_inspection_count(self):
        for rec in self:
            rec.inspection_count = len(rec.inspection_ids)

    def action_view_inspections(self):
        self.ensure_one()
        return {
            'name': _('Inspections - %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'wujia.franchise.inspection',
            'view_mode': 'list,form',
            'domain': [('franchise_id', '=', self.id)],
            'context': {'default_franchise_id': self.id},
        }

    @api.depends('inspection_ids.total_score', 'inspection_ids.grade_id', 'inspection_ids.planned_date', 'inspection_ids.state')
    def _compute_latest_inspection_info(self):
        for rec in self:
            done_inspections = rec.inspection_ids.filtered(
                lambda i: i.state in ('done', 'need_remediation') and i.planned_date
            ).sorted(
                key=lambda r: (r.planned_date, r.id),
                reverse=True
            )
            if done_inspections:
                latest = done_inspections[0]
                rec.latest_inspection_id = latest
                rec.latest_total_score = latest.total_score
                rec.latest_grade_id = latest.grade_id
                rec.latest_inspection_date = latest.planned_date

                c_count = 0
                for insp in done_inspections:
                    if insp.grade_id and insp.grade_id.name == 'C':
                        c_count += 1
                    else:
                        break
                rec.consecutive_c_count = c_count

                d_count = 0
                for insp in done_inspections:
                    if insp.grade_id and insp.grade_id.name == 'D':
                        d_count += 1
                    else:
                        break
                rec.consecutive_d_count = d_count
            else:
                rec.latest_inspection_id = False
                rec.latest_total_score = 0.0
                rec.latest_grade_id = False
                rec.latest_inspection_date = False
                rec.consecutive_c_count = 0
                rec.consecutive_d_count = 0

    @api.depends('inspection_ids.total_score', 'inspection_ids.grade_id', 'inspection_ids.planned_date', 'inspection_ids.state')
    def _compute_inspection_chart_data(self):
        for rec in self:
            inspections = rec.inspection_ids.filtered(
                lambda i: i.state in ('done', 'need_remediation') and i.planned_date
            ).sorted(
                key=lambda r: (r.planned_date, r.id),
                reverse=False
            )
            if len(inspections) > 10:
                inspections = inspections[-10:]

            labels = []
            scores = []
            grades = []
            display_scores = []
            avg_scores = []

            if inspections:
                total_sum = sum(ins.total_score for ins in inspections)
                overall_avg = total_sum / len(inspections)

                for ins in inspections:
                    date_str = ins.planned_date.strftime('%d/%m/%Y') if ins.planned_date else ''
                    labels.append(date_str)
                    scores.append(ins.total_score)
                    grade_name = (ins.grade_id.name if ins.grade_id else '').strip()
                    grades.append(grade_name)

                    score_val = ins.total_score
                    score_str = f"{int(score_val)}" if score_val.is_integer() else f"{score_val:.1f}"
                    display_text = f"{score_str} ({grade_name})" if grade_name else score_str
                    display_scores.append(display_text)
                    avg_scores.append(round(overall_avg, 2))

            rec.inspection_chart_data = json.dumps({
                'labels': labels,
                'scores': scores,
                'grades': grades,
                'display_scores': display_scores,
                'avg_scores': avg_scores,
                'title': _("Supervision Score History (Last 10 Rounds)"),
                'single_label': _("Score per Round"),
                'avg_label': _("Average Score"),
                'no_data_title': _("No Historical Data Yet!"),
                'no_data_desc': _("This store has no completed/remediation inspection sheets yet."),
            })
