# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Cross-version ORM helpers.

Odoo 17 reworked ``_read_group``: the new signature is
``_read_group(domain, groupby, aggregates)`` and it returns a list of tuples
``(group_value, aggregate, ...)``. Odoo 16 uses the older
``read_group(domain, fields, groupby)`` which returns a list of dicts. Code
authored against 19 and backported verbatim to 16 must call the right one at
runtime, so this helper normalises both to ``[(group_id, sum_value), ...]``.
"""

from odoo.release import version_info

_NEW_READ_GROUP = version_info[0] >= 17


def grouped_sum(model, domain, groupby_field, sum_field):
    """Return ``[(group_id, sum_value), ...]`` summing ``sum_field`` grouped by
    ``groupby_field``.

    ``group_id`` is the raw id of the grouped value (the integer id for a
    Many2one groupby), so callers do not depend on the record-vs-dict shape
    that differs between Odoo series.
    """
    if _NEW_READ_GROUP:
        rows = model._read_group(
            domain, [groupby_field], ['%s:sum' % sum_field],
        )
        out = []
        for group_value, total in rows:
            gid = group_value.id if hasattr(group_value, 'id') else group_value
            out.append((gid, total or 0.0))
        return out
    # Odoo 16 old API.
    rows = model.read_group(
        domain, ['%s:sum' % sum_field], [groupby_field],
    )
    out = []
    for row in rows:
        raw = row.get(groupby_field)
        gid = raw[0] if isinstance(raw, (list, tuple)) else raw
        out.append((gid, row.get(sum_field) or 0.0))
    return out


def read_group_compat(model, domain, groupby, aggregates):
    """Drop-in for the Odoo 17+ ``_read_group(domain, groupby, aggregates)``
    that also runs on Odoo 16.

    Returns the 17+ shape: a list of tuples whose first ``len(groupby)``
    elements are the grouped values (a browse record for a Many2one groupby,
    matching the new API so callers can do ``rec.id``) followed by the
    aggregate results in ``aggregates`` order. An empty ``groupby`` yields a
    single tuple of just the aggregates.
    """
    if _NEW_READ_GROUP:
        return model._read_group(domain, groupby, aggregates)
    # Odoo 16: translate to the old read_group (list of dicts). Each
    # aggregate gets a unique alias via the 'alias:func(field)' form so the
    # same source field aggregated more than once (e.g. max AND min) does not
    # collide on output name ("... is used twice").
    # Odoo 16 treats a falsey ``fields`` argument as "read every stored
    # field".  Count-only groupings must therefore still pass their group
    # keys explicitly; otherwise a small list badge can trigger a wide set of
    # unrelated aggregates (and may fail on fields that cannot be grouped).
    field_specs = list(dict.fromkeys(
        spec.split(':', 1)[0] for spec in groupby
    ))
    agg_plan = []  # (output_key, func) per aggregate, in order
    for agg in aggregates:
        if agg == '__count':
            agg_plan.append(('__count', None))
            continue
        fname, _sep, func = agg.partition(':')
        func = func or 'sum'
        alias = '%s_%s' % (fname, func)
        field_specs.append('%s:%s(%s)' % (alias, func, fname))
        agg_plan.append((alias, func))
    # Ungrouped count-only calls also need a truthy field list. Odoo 16
    # explicitly accepts and ignores this web-client pseudo-field while still
    # returning ``__count``.
    if not field_specs:
        field_specs.append('__count')
    rows = model.read_group(domain, field_specs, groupby, lazy=False)
    out = []
    for row in rows:
        values = []
        for spec in groupby:
            fname = spec.split(':')[0].split('.')[0]
            raw = row.get(spec, row.get(fname))
            field = model._fields.get(fname)
            if field is not None and field.type == 'many2one':
                rid = raw[0] if isinstance(raw, (list, tuple)) else raw
                comodel = model.env[field.comodel_name]
                values.append(comodel.browse(rid) if rid else comodel)
            else:
                values.append(raw)
        for key, func in agg_plan:
            if key == '__count':
                values.append(row.get('__count', 0))
                continue
            val = row.get(key)
            # The new API returns 0.0 for an empty :sum; old read_group
            # returns None. Coalesce sums so arithmetic callers do not hit
            # None. min/max/avg keep None (also the new-API behaviour).
            if val is None and func == 'sum':
                val = 0.0
            values.append(val)
        out.append(tuple(values))
    return out
