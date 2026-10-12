# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""All-pairs (pairwise) combination generator for scenario matrix tests.

Full cartesian products over the IFRS engine axes explode into thousands of
cases; pairwise coverage exercises every value-pair of every axis pair at a
fraction of the count while catching the interaction bugs a single-axis sweep
misses. The three riskiest engines (ECL, consolidation, leases) still run a
full product in their own test files; everything else goes through here.

Pure stdlib, deterministic output (no randomness) so a failing case number is
reproducible across runs and Odoo versions.

Usage:
    from odoo.addons.eh_account_base.tests.pairwise import pairwise_cases

    AXES = {
        'approach': ['simplified', 'general'],
        'stage': ['1', '2', '3'],
        'poci': [False, True],
        'discounting': ['none', 'eir'],
    }
    for case in pairwise_cases(AXES):
        # case is a dict: {'approach': 'general', 'stage': '2', ...}
        ...
"""

from itertools import combinations, product


def pairwise_cases(axes):
    """Return a deterministic list of dicts covering all value pairs.

    Greedy in-parameter-order construction: seed with the full product of the
    two largest axes, then extend each case so every remaining (axis, axis)
    value pair appears at least once.
    """
    if not axes:
        return []
    names = sorted(axes, key=lambda n: (-len(axes[n]), n))
    if len(names) == 1:
        return [{names[0]: v} for v in axes[names[0]]]

    # Every (axis-pair, value-pair) that must be covered.
    uncovered = set()
    for a, b in combinations(names, 2):
        for va, vb in product(axes[a], axes[b]):
            uncovered.add((a, va, b, vb))

    def covers(case):
        got = set()
        keys = sorted(case, key=names.index)
        for a, b in combinations(keys, 2):
            got.add((a, case[a], b, case[b]))
        return got

    # Seed: full product of the two widest axes.
    cases = [
        {names[0]: va, names[1]: vb}
        for va, vb in product(axes[names[0]], axes[names[1]])
    ]

    # Horizontal growth: pick, for each remaining axis, the value covering
    # the most uncovered pairs for each seeded case.
    for name in names[2:]:
        for case in cases:
            best_value, best_gain = None, -1
            for value in axes[name]:
                trial = dict(case)
                trial[name] = value
                gain = len(covers(trial) & uncovered)
                if gain > best_gain:
                    best_value, best_gain = value, gain
            case[name] = best_value
        for case in cases:
            uncovered -= covers(case)

    # Vertical growth: add cases until every pair is covered.
    while uncovered:
        a, va, b, vb = sorted(uncovered)[0]
        case = {a: va, b: vb}
        for name in names:
            if name in case:
                continue
            best_value, best_gain = None, -1
            for value in axes[name]:
                trial = dict(case)
                trial[name] = value
                gain = len(covers(trial) & uncovered)
                if gain > best_gain:
                    best_value, best_gain = value, gain
            case[name] = best_value
        cases.append(case)
        uncovered -= covers(case)

    return cases


def full_product(axes):
    """Full cartesian product as a list of dicts, deterministic order."""
    names = sorted(axes)
    return [
        dict(zip(names, values))
        for values in product(*(axes[n] for n in names))
    ]
