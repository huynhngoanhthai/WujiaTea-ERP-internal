from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaOrderWindow(models.Model):
    _name = 'wujia.order.window'
    _description = 'Portal ordering time window (per area)'
    _order = 'sequence, id'

    name = fields.Char(
        string='Window name',
        required=True,
        translate=True,
        help='e.g. "Morning window HN" — shown in the portal UI when reporting that ordering is outside the window.',
    )
    active = fields.Boolean(default=True)
    area_ids = fields.Many2many(
        'res.area',
        'wujia_order_window_res_area_rel',
        'window_id',
        'area_id',
        string='Areas',
        required=True,
        help="The window applies to franchises located in any of these areas, in each store's own local time. An area can have several windows (e.g. morning + evening) — ordering is allowed while at least one is open.",
    )
    order_time_from = fields.Float(
        string='Start time',
        required=True,
        default=10.0,
        help='Float hours 0.0–24.0. E.g. 10.5 = 10:30.',
    )
    order_time_to = fields.Float(
        string='End time',
        required=True,
        default=4.0,
        help='If < From the window runs past midnight (is_overnight=True).',
    )
    is_overnight = fields.Boolean(
        string='Overnight',
        compute='_compute_is_overnight',
        store=True,
        help='True when To < From — the window spans midnight.',
    )
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )
    description = fields.Text()

    _order_time_from_range = models.Constraint(
        'CHECK (order_time_from >= 0.0 AND order_time_from < 24.0)',
        'Start hour must be within [0, 24).',
    )
    _order_time_to_range = models.Constraint(
        'CHECK (order_time_to >= 0.0 AND order_time_to < 24.0)',
        'End hour must be within [0, 24).',
    )

    @api.depends('order_time_from', 'order_time_to')
    def _compute_is_overnight(self):
        for rec in self:
            rec.is_overnight = rec.order_time_to < rec.order_time_from

    @api.constrains('order_time_from', 'order_time_to')
    def _check_window_not_zero(self):
        for rec in self:
            if rec.order_time_from == rec.order_time_to:
                raise ValidationError(_(
                    "Window '%s' has From == To — no valid time.",
                    rec.display_name,
                ))

    @api.constrains('area_ids', 'order_time_from', 'order_time_to', 'active')
    def _check_areas(self):
        # M2M required không được ORM kiểm ⇒ kiểm ở đây, gắn vào giờ để create nào cũng chạy.
        for rec in self:
            if not rec.area_ids:
                raise ValidationError(_("Window '%s' must apply to at least one area.", rec.display_name))
            if not rec.active:
                continue
            dup = self.search([
                ('id', '!=', rec.id),
                ('area_ids', 'in', rec.area_ids.ids),
                ('order_time_from', '=', rec.order_time_from),
                ('order_time_to', '=', rec.order_time_to),
            ], limit=1)
            if dup:
                raise ValidationError(_(
                    "Window '%(name)s' duplicates '%(dup)s': same hours for area %(areas)s.",
                    name=rec.display_name, dup=dup.display_name,
                    areas=', '.join((rec.area_ids & dup.area_ids).mapped('name')),
                ))

    def is_now_open(self, now_hours):
        """Một bản ghi window có cho phép thời điểm `now_hours` không?"""
        self.ensure_one()
        f, t = self.order_time_from, self.order_time_to
        if f <= t:
            return f <= now_hours <= t
        return now_hours >= f or now_hours <= t
