# J-V0: DB đã cài 19.0.1.0.0 (local) không chạy lại <function> noupdate ⇒ bật ngôn ngữ ở đây.
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    api.Environment(cr, SUPERUSER_ID, {})['res.lang']._wj_enable_languages()
