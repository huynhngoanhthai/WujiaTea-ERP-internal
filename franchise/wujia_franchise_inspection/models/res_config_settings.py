# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'




    wujia_inspection_use_google_drive = fields.Boolean(
        string='Store Inspection Videos on Google Drive',
        help='If enabled, inspection videos will be automatically uploaded to Google Drive instead of local Odoo server storage.',
        config_parameter='wujia_franchise_inspection.use_google_drive_video',
        default=False,
    )

    google_drive_credentials_file = fields.Binary(
        string='File credentials.json',
        help='Select credentials.json file downloaded from Google Cloud Console to update OAuth config.',
    )
    google_drive_credentials_filename = fields.Char(
        string='Credentials Filename',
        default='credentials.json',
    )

    google_drive_token_file = fields.Binary(
        string='File token.json',
        help='Select token.json file containing OAuth access/refresh token to update.',
    )
    google_drive_token_filename = fields.Char(
        string='Token Filename',
        default='token.json',
    )

    google_drive_has_credentials = fields.Boolean(
        string='credentials.json Present',
        compute='_compute_drive_auth_status',
    )
    google_drive_has_token = fields.Boolean(
        string='token.json Present',
        compute='_compute_drive_auth_status',
    )
    google_drive_status_message = fields.Char(
        string='Authentication Status',
        compute='_compute_drive_auth_status',
    )

    def _get_data_file_path(self, filename):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, '..', 'data', filename)

    @api.depends('wujia_inspection_use_google_drive')
    def _compute_drive_auth_status(self):
        for rec in self:
            cred_path = rec._get_data_file_path('credentials.json')
            token_path = rec._get_data_file_path('token.json')

            has_cred = os.path.exists(cred_path)
            has_token = os.path.exists(token_path)

            rec.google_drive_has_credentials = has_cred
            rec.google_drive_has_token = has_token

            if has_cred and has_token:
                rec.google_drive_status_message = 'Both credentials.json and token.json are loaded'
            elif has_cred:
                rec.google_drive_status_message = 'credentials.json loaded (token.json missing)'
            else:
                rec.google_drive_status_message = 'Google Drive authentication files missing'

    def set_values(self):
        super().set_values()
        for rec in self:
            # 1. Lưu file credentials.json nếu người dùng tải file mới lên
            if rec.google_drive_credentials_file:
                try:
                    raw_data = base64.b64decode(rec.google_drive_credentials_file).decode('utf-8')
                    # Validate JSON format
                    json.loads(raw_data)
                    cred_path = rec._get_data_file_path('credentials.json')
                    with open(cred_path, 'w', encoding='utf-8') as f:
                        f.write(raw_data)
                    _logger.info("Successfully updated credentials.json from Settings UI.")
                except Exception as e:
                    raise UserError(_("Invalid credentials.json file format: %s") % str(e))

            # 2. Lưu file token.json nếu người dùng tải file mới lên
            if rec.google_drive_token_file:
                try:
                    raw_data = base64.b64decode(rec.google_drive_token_file).decode('utf-8')
                    # Validate JSON format
                    json.loads(raw_data)
                    token_path = rec._get_data_file_path('token.json')
                    with open(token_path, 'w', encoding='utf-8') as f:
                        f.write(raw_data)
                    _logger.info("Successfully updated token.json from Settings UI.")
                except Exception as e:
                    raise UserError(_("Invalid token.json file format: %s") % str(e))

    def action_test_google_drive_connection(self):
        """Kiểm tra kết nối và cấu trúc thư mục Google Drive ngay trên trang Cài đặt."""
        self.ensure_one()
        from .google_drive_client import GoogleDriveClient

        client = GoogleDriveClient()
        try:
            folder_id = client.get_or_create_folder('wujia media')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Google Drive Connection Successful!'),
                    'message': _("Authentication successful. 'wujia media' folder is ready (Folder ID: %s).") % folder_id,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_("Google Drive connection check failed: %s") % str(e))
