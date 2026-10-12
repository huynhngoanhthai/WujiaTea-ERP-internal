import re

from odoo import models


_FRANCHISE_CHANNEL_RE = re.compile(r'^wujia\.franchise_(\d+)$')


class IrWebsocket(models.AbstractModel):
    _inherit = 'ir.websocket'

    def _build_bus_channel_list(self, channels):
        channels = list(channels)
        requested_franchise_ids = []
        for ch in list(channels):
            if isinstance(ch, str):
                match = _FRANCHISE_CHANNEL_RE.match(ch)
                if match:
                    channels.remove(ch)
                    requested_franchise_ids.append(int(match.group(1)))

        if requested_franchise_ids and self.env.user and not self.env.user._is_public():
            allowed_franchise_ids = set(
                self.env['wujia.franchise.member'].sudo().search([
                    ('user_id', '=', self.env.user.id),
                    ('franchise_id', 'in', requested_franchise_ids),
                    ('is_currently_valid', '=', True),
                ]).mapped('franchise_id.id')
            )
            for fid in requested_franchise_ids:
                if fid in allowed_franchise_ids:
                    channels.append(f'wujia.franchise_{fid}')

        return super()._build_bus_channel_list(channels)
