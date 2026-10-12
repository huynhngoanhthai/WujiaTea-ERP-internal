# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class WujiaFranchiseRevenueComputeWizard(models.TransientModel):
    _name = 'wujia.franchise.revenue.compute.wizard'
    _description = 'Auto Calculate Revenue from File Wizard'

    revenue_id = fields.Many2one(
        'wujia.franchise.revenue',
        string='Revenue Record',
        required=True,
        readonly=True,
        ondelete='cascade',
    )
    data_file = fields.Binary(
        string='Revenue File Content',
        related='revenue_id.import_file',
        readonly=True,
    )
    file_name = fields.Char(
        string='File Name',
        related='revenue_id.import_file_name',
        readonly=True,
    )
    has_header = fields.Boolean(
        string='First Row is Header',
        default=True,
        help='Check if the first row of your file contains column names.',
    )
    column_index = fields.Selection(
        selection='_get_column_selection',
        string='Column to Sum',
        required=True,
        default='2',
        help='Select the column that contains revenue amounts to sum up.',
    )
    row_count = fields.Integer(
        string='Valid Rows Summed',
        compute='_compute_calculated_sum',
    )
    calculated_sum = fields.Monetary(
        string='Calculated Total Revenue',
        compute='_compute_calculated_sum',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='revenue_id.currency_id',
        readonly=True,
    )

    @api.model
    def _int_to_excel_col(self, n):
        """Convert 0-indexed column integer to Excel column letters (0 -> 'A', 25 -> 'Z', 26 -> 'AA')."""
        result = ""
        n = int(n) + 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result = chr(65 + remainder) + result
        return result

    @api.model
    def _get_column_selection(self):
        revenue_id = (
            self.env.context.get('default_revenue_id')
            or self.env.context.get('active_id')
            or (self.revenue_id.id if hasattr(self, 'revenue_id') and self.revenue_id else False)
        )
        revenue = self.env['wujia.franchise.revenue'].browse(revenue_id) if revenue_id else False

        if revenue and revenue.import_file:
            try:
                content = base64.b64decode(revenue.import_file)
                rows = self._parse_file_rows(content, revenue.import_file_name or 'file.csv')
                if rows:
                    first_row = rows[0]
                    selection = []
                    for idx, val in enumerate(first_row):
                        col_letter = self._int_to_excel_col(idx)
                        header_label = str(val).strip() if val else False
                        if header_label:
                            selection.append((str(idx), _("Column %s: %s", col_letter, header_label)))
                        else:
                            selection.append((str(idx), _("Column %s", col_letter)))
                    if selection:
                        return selection
            except Exception as e:
                _logger.warning("Could not read columns from file: %s", e)

        # Fallback default columns A through Z
        return [(str(i), _("Column %s", self._int_to_excel_col(i))) for i in range(26)]

    @api.depends('column_index', 'has_header', 'revenue_id.import_file')
    def _compute_calculated_sum(self):
        for rec in self:
            if not rec.revenue_id or not rec.revenue_id.import_file or not rec.column_index:
                rec.calculated_sum = 0.0
                rec.row_count = 0
                continue

            try:
                content = base64.b64decode(rec.revenue_id.import_file)
                rows = self._parse_file_rows(content, rec.revenue_id.import_file_name or 'file.csv')
            except Exception as e:
                _logger.warning("Failed to parse file for sum: %s", e)
                rec.calculated_sum = 0.0
                rec.row_count = 0
                continue

            if not rows:
                rec.calculated_sum = 0.0
                rec.row_count = 0
                continue

            start_idx = 1 if rec.has_header and len(rows) > 1 else 0
            col_target = int(rec.column_index)
            total = 0.0
            count = 0

            for row in rows[start_idx:]:
                if not row or col_target >= len(row):
                    continue
                cell_val = str(row[col_target]).strip()
                if not cell_val:
                    continue
                # Clean currency and delimiter symbols
                clean_val = (
                    cell_val.replace(',', '')
                    .replace(' ', '')
                    .replace('$', '')
                    .replace('₫', '')
                    .replace('đ', '')
                    .replace('VND', '')
                    .replace('VNĐ', '')
                )
                try:
                    num = float(clean_val)
                    total += num
                    count += 1
                except ValueError:
                    continue

            rec.calculated_sum = total
            rec.row_count = count

    def action_apply_sum(self):
        self.ensure_one()
        if not self.revenue_id:
            raise ValidationError(_("No revenue record linked to this wizard."))

        col_dict = dict(self._get_column_selection())
        col_label = col_dict.get(self.column_index, _("Column %s", self.column_index))

        self.revenue_id.write({
            'amount': self.calculated_sum,
            'source_reference': self.file_name or self.revenue_id.source_reference,
        })

        # Post message to chatter
        self.revenue_id.message_post(
            body=_(
                "Revenue amount automatically calculated from file <b>%s</b>.<br/>"
                "• Selected Column: <b>%s</b><br/>"
                "• Total Amount: <b>%s</b> (from %d data rows)",
                self.file_name or _("Uploaded File"),
                col_label,
                self.calculated_sum,
                self.row_count,
            )
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Revenue Calculated"),
                'message': _("Updated revenue to %s from %d rows in file.", self.calculated_sum, self.row_count),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def _parse_file_rows(self, file_content, file_name):
        rows = []
        ext = file_name.lower().split('.')[-1] if file_name else 'csv'
        if ext == 'csv':
            try:
                text = file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = file_content.decode('latin-1')
            reader = csv.reader(io.StringIO(text))
            for row in reader:
                rows.append(row)
        else:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(filename=io.BytesIO(file_content), data_only=True)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    rows.append([str(cell) if cell is not None else '' for cell in row])
            except Exception as e:
                _logger.warning("openpyxl failed to parse excel file: %s", e)
                try:
                    text = file_content.decode('utf-8-sig')
                    reader = csv.reader(io.StringIO(text))
                    for row in reader:
                        rows.append(row)
                except Exception:
                    raise ValidationError(_("Could not parse file. Supported formats: .csv, .xlsx, .xls."))
        return rows
