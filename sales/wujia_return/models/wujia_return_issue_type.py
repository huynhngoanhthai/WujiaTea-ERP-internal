from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class WujiaReturnIssueType(models.Model):
    """Master data — loại lỗi đổi trả/bù hàng (BA: wujia.return.issue.type).

    Rename từ wujia.return.error.type (Sprint K). Seed qua
    data/return_issue_type_data.xml."""

    _name = 'wujia.return.issue.type'
    _description = 'Wujia Return Issue Type'
    _order = 'sequence, code, id'

    name = fields.Char(string='Issue type name', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    note = fields.Text(string='Internal note', translate=True)

    @api.constrains('code')
    def _check_code_unique(self):
        for rec in self.filtered('code'):
            dup = self.sudo().search_count([
                ('code', '=', rec.code), ('id', '!=', rec.id),
            ])
            if dup:
                raise ValidationError(_("Issue type code '%s' already exists.", rec.code))

    def write(self, vals):
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        self.env.registry.clear_cache()
        return res
