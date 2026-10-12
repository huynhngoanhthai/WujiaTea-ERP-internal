# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Unit tests for the payload codec.

Covers round trip fidelity, version byte handling, None handling, large
payload compression ratio sanity, and refusal of unknown codec versions.
"""

import json

from odoo.tests import tagged

from odoo.addons.eh_account_base.tools.payload_codec import (
    compress_payload,
    decompress_payload,
    PayloadCorruptionError,
    UnsupportedPayloadVersionError,
)
from .common import EhAccountUnitTestCase


@tagged('eh_account_base', 'unit')
class TestPayloadCodec(EhAccountUnitTestCase):

    def test_round_trip_simple_dict(self):
        original = {'a': 1, 'b': 'hello', 'c': [1, 2, 3]}
        decoded = decompress_payload(compress_payload(original))
        self.assertEqual(decoded, original)

    def test_round_trip_nested(self):
        original = {
            'lines': [
                {'id': 1, 'name': 'Cash', 'columns': [{'value': 1234.56}]},
                {'id': 2, 'name': 'Bank', 'columns': [{'value': -12.0}]},
            ],
            'totals': {'debit': 1234.56, 'credit': 12.0},
            'meta': {'currency': 'AUD'},
        }
        decoded = decompress_payload(compress_payload(original))
        self.assertEqual(decoded, original)

    def test_none_returns_none(self):
        self.assertIsNone(compress_payload(None))
        self.assertIsNone(decompress_payload(None))
        self.assertIsNone(decompress_payload(b''))

    def test_version_byte_present(self):
        blob = compress_payload({'a': 1})
        self.assertEqual(blob[0], 0x01,
                         "first byte should be the codec version")

    def test_unknown_version_raises(self):
        bad_blob = bytes([0xFF]) + b'somecompressedjunk'
        with self.assertRaises(UnsupportedPayloadVersionError):
            decompress_payload(bad_blob)

    def test_invalid_base64_raises_typed_corruption(self):
        with self.assertRaisesRegex(PayloadCorruptionError, 'base64'):
            decompress_payload('not valid base64***')
        with self.assertRaisesRegex(PayloadCorruptionError, 'base64'):
            decompress_payload(b'not valid base64***')

    def test_corrupt_zlib_body_raises_typed_corruption(self):
        with self.assertRaisesRegex(PayloadCorruptionError, 'zlib'):
            decompress_payload(b'\x01not-zlib')

    def test_corrupt_json_body_raises_typed_corruption(self):
        import zlib
        with self.assertRaisesRegex(PayloadCorruptionError, 'JSON'):
            decompress_payload(b'\x01' + zlib.compress(b'{bad json'))

    def test_valid_base64_unknown_version_remains_typed_version_error(self):
        import base64
        encoded = base64.b64encode(b'\xffunknown-version')
        with self.assertRaises(UnsupportedPayloadVersionError):
            decompress_payload(encoded)

    def test_large_payload_compresses_well(self):
        # Repetitive payload should compress to a small fraction.
        original = {'rows': [{'k': 'value' * 10} for _ in range(1000)]}
        raw_size = len(json.dumps(original).encode('utf-8'))
        compressed_size = len(compress_payload(original))
        self.assertLess(
            compressed_size, raw_size // 4,
            f"compression ratio worse than 4x: {raw_size} -> {compressed_size}",
        )

    def test_default_str_handles_non_serialisable(self):
        # Datetime objects are not JSON serialisable by default; default=str
        # is used by the codec to fall back on stringification.
        from datetime import datetime
        original = {'when': datetime(2026, 4, 30, 12, 0, 0)}
        blob = compress_payload(original)
        decoded = decompress_payload(blob)
        # The datetime survives as a string.
        self.assertIsInstance(decoded['when'], str)
        self.assertIn('2026', decoded['when'])
