# -*- coding: utf-8 -*-
from odoo import api, fields, models


class WujiaMobileMixin(models.AbstractModel):
    """Abstract model providing core helper methods for Wujia mobile views.

    Inherit this mixin in child models using:
        _inherit = ['wujia.mobile.mixin']
    to obtain standardized status badge CSS classes and mobile summary dicts.
    """

    _name = 'wujia.mobile.mixin'
    _description = 'Wujia Mobile Core Mixin'

    @api.model
    def get_mobile_badge_class(self, state_value, style='bem'):
        """Map standard lifecycle state strings to Wujia mobile badge CSS classes.

        :param str state_value: Technical state value (e.g. 'draft', 'sale', 'done', 'cancel').
        :param str style: 'bem' for wj_mobile_badge--* or 'legacy' for bg-wujia-*. Default: 'bem'.
        :return str: Standardized CSS class name for UI badges.
        """
        if not state_value:
            return 'wj_mobile_badge--neutral' if style == 'bem' else 'bg-wujia-muted'

        state_str = str(state_value).lower()
        success_states = {'sale', 'done', 'working', 'effective', 'posted', 'approved', 'ok'}
        warning_states = {'draft', 'sent', 'scheduled', 'loading', 'delivering', 'pending', 'warning'}
        danger_states = {'cancel', 'cancelled', 'expired', 'suspended', 'rejected', 'error'}
        info_states = {'assigned', 'in_progress', 'to_approve', 'info'}

        if style == 'bem':
            if state_str in success_states:
                return 'wj_mobile_badge--success'
            elif state_str in warning_states:
                return 'wj_mobile_badge--warning'
            elif state_str in danger_states:
                return 'wj_mobile_badge--danger'
            elif state_str in info_states:
                return 'wj_mobile_badge--info'
            return 'wj_mobile_badge--neutral'

        # Legacy style
        if state_str in success_states:
            return 'bg-wujia-success'
        elif state_str in warning_states:
            return 'bg-wujia-warning'
        elif state_str in danger_states:
            return 'bg-wujia-danger'
        elif state_str in info_states:
            return 'bg-wujia-info'

        return 'bg-wujia-secondary'

    def get_mobile_summary(self):
        """Return a standardized dictionary containing basic record attributes for mobile rendering.

        :return dict: Record metadata useful for custom mobile API or rendering.
        """
        self.ensure_one()
        state_val = getattr(self, 'state', False)
        name_val = getattr(self, 'display_name', self.name if hasattr(self, 'name') else str(self.id))
        return {
            'id': self.id,
            'model': self._name,
            'name': name_val,
            'state': state_val,
            'badge_class': self.get_mobile_badge_class(state_val, style='bem'),
        }
