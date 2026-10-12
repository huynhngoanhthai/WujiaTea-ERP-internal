# -*- coding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""Compatibility shim for odoo.tools.SQL on Odoo series that predate it.

The composable ``odoo.tools.SQL`` wrapper was introduced in Odoo 17. The
reporting engine in this suite is authored against it. On Odoo 16 (which has
no such class) the backport tool rewrites ``from odoo.tools import SQL`` to
import this drop-in replacement, and rewrites ``cr.execute(sql)`` to
``cr.execute(*sql)`` so the cursor receives the rendered ``(code, params)``
pair that 16 expects.

The class reproduces the public surface the suite relies on: construction
from a ``%s``-format string plus positional SQL/value arguments, the ``code``
and ``params`` properties, ``identifier``, ``join``, and tuple-style
unpacking via ``__iter__``. The tree-flattening semantics mirror the upstream
implementation so the rendered SQL and parameter order are identical.

This module is only ever imported by the 16 backport; on 17/18/19 the suite
uses the framework's own SQL class.
"""
from __future__ import annotations

import re

IDENT_RE = re.compile(r'^[a-z0-9_][a-z0-9_$\-]*$', re.I)


class SQL:
    """Wrap SQL code with its parameters, composably (see module docstring)."""

    __slots__ = ('_code', '_args')

    def __new__(cls, code="", *args):
        if isinstance(code, SQL):
            return code
        if args:
            # Validate the placeholder count the same way upstream does.
            code % tuple("" for _ in args)
        self = object.__new__(cls)
        self._code = code
        self._args = args
        return self

    @property
    def code(self):
        stack = []
        for node in self._postfix():
            if not isinstance(node, SQL):
                stack.append("%s")
            else:
                arity = len(node._args)
                if not arity:
                    stack.append(node._code)
                    continue
                stack[-arity:] = [node._code % tuple(stack[-arity:])]
        return stack[0] if stack else ""

    @property
    def params(self):
        return [node for node in self._postfix() if not isinstance(node, SQL)]

    def _postfix(self):
        stack = [(self, False)]
        while stack:
            node, ispostfix = stack.pop()
            if ispostfix or not isinstance(node, SQL):
                yield node
            else:
                stack.append((node, True))
                stack.extend((arg, False) for arg in reversed(node._args))

    def __repr__(self):
        return "SQL(%s)" % ', '.join(map(repr, [self.code, *self.params]))

    def __bool__(self):
        return bool(self._code)

    def __eq__(self, other):
        return (isinstance(other, SQL)
                and self.code == other.code and self.params == other.params)

    def __hash__(self):
        return hash((self.code, tuple(self.params)))

    def __iter__(self):
        yield self.code
        yield self.params

    def join(self, args):
        args = list(args)
        if len(args) == 0:
            return SQL()
        if len(args) == 1:
            return SQL("%s", args[0]) if not isinstance(args[0], SQL) \
                else args[0]
        if not self._args:
            return SQL(self._code.join("%s" for _ in args), *args)
        items = [self] * (len(args) * 2 - 1)
        for index, arg in enumerate(args):
            items[index * 2] = arg
        return SQL("%s" * len(items), *items)

    @classmethod
    def identifier(cls, name, subname=None):
        assert name.isidentifier() or IDENT_RE.match(name), \
            "%r invalid for SQL.identifier()" % name
        if subname is None:
            return cls('"%s"' % name)
        assert subname.isidentifier() or IDENT_RE.match(subname), \
            "%r invalid for SQL.identifier()" % subname
        return cls('"%s"."%s"' % (name, subname))
