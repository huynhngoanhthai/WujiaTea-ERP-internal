# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
"""Shared helpers for multi-language / multi-currency dashboard payloads."""

from odoo import _


def serialize_currency(currency):
    """Return a JSON-safe currency dict for OWL formatting, or False."""
    if not currency:
        return False
    return {
        'id': currency.id,
        'name': currency.name,  # ISO code e.g. USD — used by Intl
        'symbol': currency.symbol or currency.name,
        'position': currency.position,
        'decimal_places': currency.decimal_places,
        'full_name': currency.currency_unit_label or currency.name,
    }


def resolve_display_currency(env, item=None, company=None, explicit=None):
    """
    Resolve currency for dashboard display.

    Order: explicit currency → item.currency_id → company currency → env.company.
    """
    if explicit:
        return explicit
    if item is not None and getattr(item, 'currency_id', None) and item.currency_id:
        return item.currency_id
    company = company or (item.company_id if item is not None and item.company_id else env.company)
    return company.currency_id if company else env.company.currency_id


def is_lang_rtl(lang_code):
    """Return True if language code uses an RTL script."""
    if not lang_code:
        return False
    code = str(lang_code).lower().replace('-', '_').split('_')[0]
    return code in {
        'ar', 'fa', 'he', 'ur', 'yi', 'ps', 'sd', 'ug', 'dv',
    }


def effective_layout_rtl(dashboard, lang_code=None):
    """
    Decide RTL for a dashboard given layout_direction / legacy is_rtl and user lang.
    """
    if not dashboard:
        return is_lang_rtl(lang_code)
    if getattr(dashboard, 'is_rtl', False):
        return True
    direction = getattr(dashboard, 'layout_direction', None) or 'auto'
    if direction == 'rtl':
        return True
    if direction == 'ltr':
        return False
    return is_lang_rtl(lang_code)


# Translated date-filter labels for emails / server-side rendering
DATE_FILTER_LABELS = {
    'none': lambda: _('None (All Time)'),
    'today': lambda: _('Today'),
    'yesterday': lambda: _('Yesterday'),
    'tomorrow': lambda: _('Tomorrow'),
    'this_week': lambda: _('This Week'),
    'this_month': lambda: _('This Month'),
    'this_quarter': lambda: _('This Quarter'),
    'this_year': lambda: _('This Year'),
    'week_to_date': lambda: _('Week to Date'),
    'month_to_date': lambda: _('Month to Date'),
    'year_to_date': lambda: _('Year to Date'),
    'last_7_days': lambda: _('Last 7 Days'),
    'last_30_days': lambda: _('Last 30 Days'),
    'last_90_days': lambda: _('Last 90 Days'),
    'last_week': lambda: _('Last Week'),
    'last_month': lambda: _('Last Month'),
    'last_quarter': lambda: _('Last Quarter'),
    'last_year': lambda: _('Last Year'),
    'past_until_now': lambda: _('Past Until Now'),
    'future_starting_now': lambda: _('Future Starting Now'),
    'next_week': lambda: _('Next Week'),
    'next_month': lambda: _('Next Month'),
    'next_quarter': lambda: _('Next Quarter'),
    'next_year': lambda: _('Next Year'),
}


def date_filter_label(key):
    factory = DATE_FILTER_LABELS.get(key)
    return factory() if factory else key
