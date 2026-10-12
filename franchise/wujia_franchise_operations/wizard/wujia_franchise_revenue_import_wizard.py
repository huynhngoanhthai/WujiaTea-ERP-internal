# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WujiaFranchiseRevenueImportWizard(models.TransientModel):
    _name = 'wujia.franchise.revenue.import.wizard'
    _description = 'Import Daily Revenue Records Wizard'

    data_file = fields.Binary(string='Data File', required=True, help='Upload Excel (.xlsx, .xls) or CSV (.csv) file.')
    file_name = fields.Char(string='File Name', required=True)
    default_franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Default Store',
        help='Fallback store if store code is omitted in file rows.',
    )

    def action_import(self):
        self.ensure_one()
        if not self.file_name:
            raise ValidationError(_("File name is missing."))

        ext = self.file_name.lower().split('.')[-1]
        if ext in ('xlsx', 'xls'):
            source_val = 'excel'
        elif ext == 'csv':
            source_val = 'csv'
        else:
            raise ValidationError(_("Unsupported file format (%s). Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.", ext))

        file_content = base64.b64decode(self.data_file)
        rows = self._parse_file_rows(file_content, ext)

        if not rows:
            raise ValidationError(_("The uploaded file contains no data rows to import."))

        created_records = self.env['wujia.franchise.revenue']
        skipped_count = 0
        imported_count = 0

        for row_idx, row in enumerate(rows, start=1):
            if not row or all(str(val).strip() == '' for val in row):
                continue

            # Skip header row if first row contains non-numeric text for amount
            if row_idx == 1:
                col2_str = str(row[2]).strip() if len(row) > 2 else ''
                try:
                    float(col2_str.replace(',', ''))
                except ValueError:
                    # Row 1 is header, skip
                    continue

            store_ref = str(row[0]).strip() if len(row) > 0 else ''
            date_str = str(row[1]).strip() if len(row) > 1 else ''
            amount_str = str(row[2]).strip() if len(row) > 2 else '0'
            note_str = str(row[3]).strip() if len(row) > 3 else ''

            # Resolve Store
            franchise = False
            if store_ref:
                franchise = self.env['wujia.franchise.management'].search([
                    '|', ('code', '=ilike', store_ref), ('name', '=ilike', store_ref)
                ], limit=1)
            if not franchise:
                franchise = self.default_franchise_id

            if not franchise:
                raise ValidationError(_("Row %d: Store '%s' could not be resolved and no default store was selected.", row_idx, store_ref))

            # Resolve Business Date
            business_date = self._parse_date(date_str, row_idx)

            # Resolve Amount
            try:
                amount = float(amount_str.replace(',', ''))
            except ValueError:
                raise ValidationError(_("Row %d: Invalid revenue amount '%s'.", row_idx, amount_str))

            if amount < 0:
                raise ValidationError(_("Row %d: Revenue amount (%s) cannot be negative.", row_idx, amount))

            # Check Idempotency for daily revenue
            existing = self.env['wujia.franchise.revenue'].search([
                ('franchise_id', '=', franchise.id),
                ('business_date', '=', business_date),
                ('state', 'in', ('draft', 'confirmed')),
            ], limit=1)
            if existing:
                skipped_count += 1
                _logger.info("Import skipped duplicate revenue record for store %s date %s", franchise.name, business_date)
                continue

            new_rec = self.env['wujia.franchise.revenue'].create({
                'franchise_id': franchise.id,
                'business_date': business_date,
                'amount': amount,
                'source': source_val,
                'source_reference': self.file_name,
                'note': note_str or _("Imported from file %s", self.file_name),
            })
            created_records |= new_rec
            imported_count += 1

        message = _("Import process completed! Imported: %d records. Skipped duplicates: %d.", imported_count, skipped_count)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Revenue Import Success"),
                'message': message,
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _("Daily Revenues"),
                    'res_model': 'wujia.franchise.revenue',
                    'view_mode': 'list,form',
                    'domain': [('id', 'in', created_records.ids)] if created_records else [],
                }
            }
        }

    def _parse_file_rows(self, file_content, ext):
        rows = []
        if ext == 'csv':
            try:
                text = file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = file_content.decode('latin-1')
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                rows.append(row)
        else:
            # Excel parsing via openpyxl
            try:
                import openpyxl
                wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    rows.append([str(cell) if cell is not None else '' for cell in row])
            except Exception as e:
                _logger.warning("openpyxl failed to parse excel file: %s", e)
                # Fallback text parsing if CSV disguised as xls
                try:
                    text = file_content.decode('utf-8-sig')
                    reader = csv.reader(io.StringIO(text))
                    for row in reader:
                        rows.append(row)
                except Exception:
                    raise ValidationError(_("Could not parse Excel file. Please ensure openpyxl is available or upload a CSV file."))
        return rows

    def _parse_date(self, date_str, row_idx):
        if not date_str:
            return fields.Date.context_today(self)
        
        # Clean date string if contains time component
        date_str = date_str.split(' ')[0].split('T')[0].strip()

        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return fields.Date.to_string(dt.date())
            except ValueError:
                continue

        raise ValidationError(_("Row %d: Invalid business date '%s'. Allowed formats: YYYY-MM-DD or DD/MM/YYYY.", row_idx, date_str))
