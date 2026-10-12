# Copyright (C) NexGen Solutions
import json
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class DynamicDashboardImportWizard(models.TransientModel):
    _name = 'dynamic.dashboard.import.wizard'
    _description = 'Import Dynamic Dashboard'

    import_file = fields.Binary(string='Upload JSON File', required=True)
    file_name = fields.Char(string='File Name')

    def action_import(self):
        if not self.import_file:
            raise UserError(_("Please upload a file."))
        
        try:
            file_content = base64.b64decode(self.import_file).decode('utf-8')
            data = json.loads(file_content)
        except Exception as e:
            raise UserError(_("Invalid JSON file. Error: %s" % str(e)))
        
        if 'name' not in data or 'items' not in data:
            raise UserError(_("Invalid Dashboard JSON format."))
            
        dashboard_vals = {
            'name': data['name'] + ' (Imported)',
        }
        dashboard = self.env['dynamic.dashboard'].create(dashboard_vals)
        
        for item_data in data['items']:
            item_vals = {
                'dashboard_id': dashboard.id,
                'name': item_data.get('name'),
                'item_type': item_data.get('item_type'),
                'tile_color': item_data.get('tile_color'),
                'tile_icon': item_data.get('tile_icon'),
                'data_calculation_type': item_data.get('data_calculation_type'),
                'data_type': item_data.get('data_type'),
                'group_by_date_type': item_data.get('group_by_date_type'),
                'sub_group_by_date_type': item_data.get('sub_group_by_date_type'),
                'sort_order': item_data.get('sort_order', 'desc'),
                'record_limit': item_data.get('record_limit'),
                'enable_target': item_data.get('enable_target'),
                'standard_target_value': item_data.get('standard_target_value'),
                'target_view': item_data.get('target_view'),
                'chart_theme': item_data.get('chart_theme'),
                'is_stacked': item_data.get('is_stacked'),
                'show_data_value': item_data.get('show_data_value'),
                'grid_x': item_data.get('grid_x'),
                'grid_y': item_data.get('grid_y'),
                'grid_w': item_data.get('grid_w'),
                'grid_h': item_data.get('grid_h'),
            }
            
            # Resolve Model & Fields
            model_id = self.env['ir.model'].search([('model', '=', item_data.get('model_id'))], limit=1)
            if model_id:
                item_vals['model_id'] = model_id.id
                
                if item_data.get('measure_field_ids'):
                    measure_fields = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', 'in', item_data['measure_field_ids'])])
                    if measure_fields: item_vals['measure_field_ids'] = [(6, 0, measure_fields.ids)]

                if item_data.get('measure_field_2_ids'):
                    measure_fields_2 = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', 'in', item_data['measure_field_2_ids'])])
                    if measure_fields_2: item_vals['measure_field_2_ids'] = [(6, 0, measure_fields_2.ids)]
                    
                if item_data.get('list_view_field_ids'):
                    list_view_fields = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', 'in', item_data['list_view_field_ids'])])
                    if list_view_fields: item_vals['list_view_field_ids'] = [(6, 0, list_view_fields.ids)]
                
                if item_data.get('group_by_field_id'):
                    groupby_field = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', '=', item_data['group_by_field_id'])], limit=1)
                    if groupby_field: item_vals['group_by_field_id'] = groupby_field.id
                
                if item_data.get('sub_group_by_field_id'):
                    subgroupby_field = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', '=', item_data['sub_group_by_field_id'])], limit=1)
                    if subgroupby_field: item_vals['sub_group_by_field_id'] = subgroupby_field.id
                
                if item_data.get('sort_by_field_id'):
                    sortby_field = self.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', '=', item_data['sort_by_field_id'])], limit=1)
                    if sortby_field: item_vals['sort_by_field_id'] = sortby_field.id
                    
            self.env['dynamic.dashboard.item'].create(item_vals)
            
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dynamic.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current',
        }
