# -*- coding: utf-8 -*-

import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class WujiaFieldsValue(models.TransientModel):
    _name = 'wujia.fields.value'
    _description = 'Wujia View Fields Value Wizard'

    res_id = fields.Integer(string='Resource ID')
    model = fields.Char(string='Model Name')
    model_id = fields.Many2one('ir.model', string='Model')
    res_display_name = fields.Char(string='Record ID', compute='_compute_res_display_name')
    field_ids = fields.Many2many('ir.model.fields', string='Filter Fields')
    field_value_line_ids = fields.One2many('wujia.fields.value.line', 'wizard_id', string='Field Values')

    @api.model
    def default_get(self, fields_list):
        """Resolve model_id from model name and pre-populate field lines when opening wizard via context."""
        res = super().default_get(fields_list)
        model_name = res.get('model') or self.env.context.get('default_model')
        res_id = res.get('res_id') or self.env.context.get('default_res_id')

        if model_name:
            res['model'] = model_name
            model_rec = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            if model_rec:
                res['model_id'] = model_rec.id
                if res_id and model_name in self.env:
                    target_record = self.env[model_name].browse(res_id).exists()
                    if target_record:
                        field_recs = model_rec.field_id
                        line_vals = self._build_line_vals_list(target_record, field_recs)
                        res['field_value_line_ids'] = [(0, 0, v) for v in line_vals]

        if res_id:
            res['res_id'] = res_id

        return res

    def _build_line_vals_list(self, target_record, field_recs):
        """Build dictionary values for field value lines."""
        line_vals_list = []
        idx = 1
        for field in field_recs:
            if field.name == 'id':
                continue

            if field.relation:
                field_type_str = f"{field.ttype} ({field.relation})"
            else:
                field_type_str = field.ttype

            rel_model = False
            rel_res_id = False
            rel_res_ids = False
            has_relation = False

            try:
                val = getattr(target_record.sudo(), field.name, None)
            except Exception as e:
                val_str = f"<Error reading field: {e}>"
            else:
                if isinstance(val, models.BaseModel):
                    if field.ttype == 'many2one':
                        if val:
                            val_str = f"({val.id}, {repr(val.display_name or str(val.id))})"
                            rel_model = val._name
                            rel_res_id = val.id
                            has_relation = True
                        else:
                            val_str = "False"
                            rel_model = field.relation
                    else:
                        if val:
                            rel_model = val._name
                            rel_res_ids = json.dumps(val.ids)
                            has_relation = True
                            tuple_items = [f"({r.id}, {repr(r.display_name or str(r.id))})" for r in val[:10]]
                            if len(val) > 10:
                                val_str = f"[{', '.join(tuple_items)}, ... ({len(val)} records total)]"
                            else:
                                val_str = f"[{', '.join(tuple_items)}]"
                        else:
                            val_str = "[]"
                            rel_model = field.relation
                elif val is not None:
                    val_str = str(val)
                else:
                    val_str = ""

            line_vals_list.append({
                'sequence': idx,
                'field_name': field.name,
                'field_label': field.field_description or field.name,
                'field_type': field_type_str,
                'field_value': val_str,
                'relation_model': rel_model,
                'relation_res_id': rel_res_id,
                'relation_res_ids': rel_res_ids,
                'has_relation': has_relation,
            })
            idx += 1
        return line_vals_list

    @api.model_create_multi
    def create(self, vals_list):
        """Populate field_value_line_ids on create if not already supplied."""
        records = super().create(vals_list)
        for rec in records:
            if rec.model_id and not rec.model:
                rec.model = rec.model_id.model
            elif rec.model and not rec.model_id:
                rec.model_id = self.env['ir.model'].search([('model', '=', rec.model)], limit=1)
            if not rec.field_value_line_ids:
                rec._generate_field_value_lines()
        return records

    def _generate_field_value_lines(self):
        """Generate field value lines for the current wizard record."""
        self.ensure_one()
        self.field_value_line_ids.unlink()

        if not (self.model_id and self.res_id and self.model_id.model in self.env):
            return

        target_model = self.model_id.model
        target_record = self.env[target_model].browse(self.res_id).exists()
        if not target_record:
            return

        field_recs = self.field_ids if self.field_ids else self.model_id.field_id
        line_vals = self._build_line_vals_list(target_record, field_recs)
        for v in line_vals:
            v['wizard_id'] = self.id
        if line_vals:
            self.env['wujia.fields.value.line'].create(line_vals)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if self.model_id:
            self.model = self.model_id.model
        else:
            self.model = False

    @api.onchange('model')
    def _onchange_model(self):
        if self.model:
            self.model_id = self.env['ir.model'].search([('model', '=', self.model)], limit=1)
        else:
            self.model_id = False

    @api.depends('res_id')
    def _compute_res_display_name(self):
        for rec in self:
            rec.res_display_name = str(rec.res_id) if rec.res_id else ""

    def action_reload_fields(self):
        """Reload field values when user changes model_id, res_id, or field_ids."""
        self.ensure_one()
        # Sync model <-> model_id
        if self.model_id and not self.model:
            self.model = self.model_id.model
        elif self.model and not self.model_id:
            self.model_id = self.env['ir.model'].search([('model', '=', self.model)], limit=1)
        self._generate_field_value_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': _('View Fields Value'),
            'res_model': 'wujia.fields.value',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class WujiaFieldsValueLine(models.TransientModel):
    _name = 'wujia.fields.value.line'
    _description = 'Wujia View Fields Value Line'

    wizard_id = fields.Many2one('wujia.fields.value', string='Wizard', ondelete='cascade')
    sequence = fields.Integer(string='#', default=10)
    field_name = fields.Char(string='Field Technical Name')
    field_label = fields.Char(string='Field Label')
    field_type = fields.Char(string='Field Type')
    field_value = fields.Text(string='Value')
    relation_model = fields.Char(string='Relation Model')
    relation_res_id = fields.Integer(string='Relation Resource ID')
    relation_res_ids = fields.Char(string='Relation Resource IDs')
    has_relation = fields.Boolean(string='Has Relation')

    def action_view_detail(self):
        self.ensure_one()

        target_res_id = False
        if self.relation_res_id:
            target_res_id = self.relation_res_id
        elif self.relation_res_ids:
            try:
                res_ids = json.loads(self.relation_res_ids)
                if res_ids:
                    target_res_id = res_ids[0]
            except Exception:
                pass

        if self.has_relation and self.relation_model and target_res_id:
            target_model_id = self.env['ir.model'].search([('model', '=', self.relation_model)], limit=1)
            new_wizard = self.env['wujia.fields.value'].create({
                'model': self.relation_model,
                'model_id': target_model_id.id if target_model_id else False,
                'res_id': target_res_id,
                'field_ids': [(5, 0, 0)],
            })
            return {
                'type': 'ir.actions.act_window',
                'name': _('View Fields Value'),
                'res_model': 'wujia.fields.value',
                'res_id': new_wizard.id,
                'view_mode': 'form',
                'target': 'new',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Value Detail'),
            'res_model': 'wujia.fields.value.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_target_record(self):
        self.ensure_one()
        if not self.relation_model:
            raise UserError(_("No target relation model defined for this field."))

        if self.relation_res_id:
            return {
                'type': 'ir.actions.act_window',
                'name': f"{self.field_label or self.field_name} ({self.relation_model})",
                'res_model': self.relation_model,
                'res_id': self.relation_res_id,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.relation_res_ids:
            try:
                res_ids = json.loads(self.relation_res_ids)
            except Exception:
                res_ids = []
            if res_ids:
                return {
                    'type': 'ir.actions.act_window',
                    'name': f"{self.field_label or self.field_name} ({self.relation_model})",
                    'res_model': self.relation_model,
                    'domain': [('id', 'in', res_ids)],
                    'view_mode': 'list,form',
                    'target': 'current',
                }

        raise UserError(_("No target record available to open."))



