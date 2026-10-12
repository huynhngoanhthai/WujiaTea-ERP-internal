from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models


CONFIG_KEY_FROM = 'wujia_portal.portal_order_time_from'
CONFIG_KEY_TO = 'wujia_portal.portal_order_time_to'
CONFIG_KEY_ENABLED = 'wujia_portal.portal_order_time_limit_enabled'

DEFAULT_FROM = 10.0
DEFAULT_TO = 4.0
DEFAULT_ENABLED = True


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Global fallback (áp dụng khi khu vực chưa cấu hình `wujia.order.window`).
    portal_order_time_from = fields.Float(
        string='Portal Order Time From (fallback)',
        config_parameter=CONFIG_KEY_FROM,
        default=DEFAULT_FROM,
        help='Default start hour (float 0.0–24.0) used when the area has no window of its own.',
    )
    portal_order_time_to = fields.Float(
        string='Portal Order Time To (fallback)',
        config_parameter=CONFIG_KEY_TO,
        default=DEFAULT_TO,
        help='Default end hour (float 0.0–24.0). If To < From the window runs past midnight.',
    )
    portal_order_time_limit_enabled = fields.Boolean(
        string='Enable Portal Order Time Limit',
        config_parameter=CONFIG_KEY_ENABLED,
        default=DEFAULT_ENABLED,
        help="Enable/disable the portal ordering time window. When off, ordering is allowed at any time regardless of `wujia.order.window`.",
    )

    # -------------------- helpers (class methods on env) --------------------
    @api.model
    def _get_portal_order_window(self):
        """Read 3 global config params (fallback). Default if missing."""
        ICP = self.env['ir.config_parameter'].sudo()

        def _to_float(key, default):
            raw = ICP.get_param(key)
            if raw in (False, None, ''):
                return default
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        return {
            'from': _to_float(CONFIG_KEY_FROM, DEFAULT_FROM),
            'to': _to_float(CONFIG_KEY_TO, DEFAULT_TO),
            'enabled': ICP.get_param(CONFIG_KEY_ENABLED, 'True') in ('True', 'true', '1', True),
            # False = chưa ai lưu cấu hình chung; nơi gọi tự quyết cách báo "chưa cấu hình".
            'configured': ICP.get_param(CONFIG_KEY_FROM) not in (False, None, ''),
        }

    @api.model
    def _utc_now(self):
        return datetime.now(pytz.UTC)

    @api.model
    def _store_tz(self, franchise):
        tz_name = franchise and franchise.sudo().partner_id.tz
        return tz_name if tz_name in pytz.all_timezones_set else False

    @api.model
    def _is_within_order_window(self, franchise=None):
        """Khung giờ của cửa hàng, tính theo giờ địa phương của chính cửa hàng.

        Tắt global ⇒ luôn mở · cửa hàng thiếu tz ⇒ chặn (`tz_missing`) · window active có
        area của cửa hàng ⇒ mở khi BẤT KỲ window nào mở · không window nào khớp ⇒ khung chung.
        Dict luôn có 'from', 'to', 'enabled', 'configured', 'source', 'windows', 'open_window',
        'tz', 'tz_label', 'now' (giờ thập phân), 'today'.
        """
        global_cfg = self._get_portal_order_window()
        if not global_cfg['enabled']:
            return True, dict(global_cfg, source='global', windows=[], open_window=None,
                              tz=False, tz_label='', now=0.0, today=fields.Date.today())

        tz_name = self._store_tz(franchise)
        if not tz_name:
            return False, dict(global_cfg, source='global', windows=[], open_window=None,
                               tz=False, tz_label='', now=0.0, today=fields.Date.today(),
                               tz_missing=True)
        local = self._utc_now().astimezone(pytz.timezone(tz_name))
        now = local.hour + local.minute / 60.0 + local.second / 3600.0
        offset = local.strftime('%z')
        base = {
            'enabled': True,
            'configured': global_cfg['configured'],
            'tz': tz_name,
            'tz_label': '%s (UTC%s:%s)' % (tz_name, offset[:3], offset[3:]),
            'now': now,
            'today': local.date(),
        }

        area = franchise.sudo().area_id
        windows = self.env['wujia.order.window'].sudo().search(
            [('area_ids', 'in', area.ids)]) if area else []
        if windows:
            opened = windows.filtered(lambda w: w.is_now_open(now))[:1]
            first = opened or windows[0]
            return bool(opened), dict(
                base,
                configured=True,
                source='area:%s' % area.id,
                window_count=len(windows),
                window_name=first.name,
                **{'from': first.order_time_from, 'to': first.order_time_to},
                windows=[
                    {'name': w.name, 'from': w.order_time_from, 'to': w.order_time_to}
                    for w in windows
                ],
                open_window=opened and {'name': opened.name, 'from': opened.order_time_from,
                                        'to': opened.order_time_to},
            )

        f, t = global_cfg['from'], global_cfg['to']
        allowed = (f <= now <= t) if f <= t else (now >= f or now <= t)
        win = {'name': '', 'from': f, 'to': t}
        return allowed, dict(base, source='global', windows=[win],
                             open_window=win if allowed else None, **{'from': f, 'to': t})

    @api.model
    def _next_order_window(self, franchise=None):
        """Lần mở gần nhất (giờ + ngày địa phương cửa hàng) cho màn "ngoài khung giờ".

        Return dict {'from', 'to', 'name', 'date', 'is_today'} — hoặc None khi tắt giới hạn,
        cửa hàng thiếu tz hoặc không có khung nào.
        """
        _allowed, window = self._is_within_order_window(franchise=franchise)
        windows = window.get('windows') or []
        if not window.get('enabled') or not windows:
            return None
        now = window['now']
        best = min(windows, key=lambda w: (0 if now < (w['from'] or 0.0) else 1, w['from'] or 0.0))
        day_offset = 0 if now < (best['from'] or 0.0) else 1
        return {
            'from': best['from'] or 0.0,
            'to': best['to'] or 0.0,
            'name': best.get('name') or '',
            'date': window['today'] + timedelta(days=day_offset),
            'is_today': day_offset == 0,
        }

