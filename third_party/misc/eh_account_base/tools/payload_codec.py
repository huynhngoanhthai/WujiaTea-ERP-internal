# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Compression codec for cached report payloads.

zlib gives us roughly 5x to 10x ratio on JSON heavy report data with cheap
CPU. The codec is centralised here so the orchestrator and the audit model
agree on the format. Forward compatibility: a one byte version prefix
identifies the codec, so future formats (lz4, zstd) can coexist without
breaking stored cache entries.
"""

import base64
import binascii
import json
import zlib

# Codec version byte. Increment when changing the encoding so old payloads
# can be detected and either decoded with the legacy path or invalidated.
_CODEC_VERSION_ZLIB_JSON = 0x01


class PayloadCodecError(ValueError):
    """Base error exposed by cached-payload storage boundaries."""


class PayloadCorruptionError(PayloadCodecError):
    """Stored bytes cannot be decoded as valid payload content."""


class UnsupportedPayloadVersionError(PayloadCodecError):
    """Stored bytes use a codec version this build cannot read."""


def _reject_non_json_constant(value):
    raise ValueError("non-finite JSON constant: %s" % value)


def _binary_field_bytes(blob):
    """Normalize raw or Odoo Binary/base64 storage to bytes, strictly."""
    if isinstance(blob, str):
        try:
            encoded = blob.encode('ascii')
        except UnicodeEncodeError as exc:
            raise PayloadCorruptionError(
                "payload base64 contains non-ASCII characters"
            ) from exc
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PayloadCorruptionError("payload base64 is invalid") from exc
    if isinstance(blob, memoryview):
        blob = blob.tobytes()
    if isinstance(blob, bytearray):
        blob = bytes(blob)
    if not isinstance(blob, bytes):
        raise PayloadCorruptionError(
            "payload must be bytes, bytearray, memoryview, or base64 text"
        )
    if not blob or blob[0] == _CODEC_VERSION_ZLIB_JSON:
        return blob

    # Unknown raw versions use a non-base64 prefix byte. Printable/base64
    # bytes are Odoo Binary storage and must decode strictly; never swallow a
    # padding/alphabet error and reinterpret corrupt storage as a version.
    base64_alphabet = (
        b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
    )
    if blob[0] not in base64_alphabet:
        return blob
    try:
        return base64.b64decode(blob, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PayloadCorruptionError("payload base64 is invalid") from exc


def compress_payload(payload):
    """Serialise a Python value to a compressed bytes blob.

    :param payload: any JSON serialisable Python object.
    :return: bytes (a one byte version prefix followed by the compressed body).
    """
    if payload is None:
        return None
    body = json.dumps(payload, separators=(',', ':'), default=str).encode('utf-8')
    return bytes([_CODEC_VERSION_ZLIB_JSON]) + zlib.compress(body)


def decompress_payload(blob):
    """Decompress a payload produced by compress_payload().

    Returns None if blob is None or empty. Raises a typed PayloadCodecError
    for unsupported versions or corrupt base64, zlib, UTF-8, or JSON.
    """
    if not blob:
        return None
    blob = _binary_field_bytes(blob)
    if not blob:
        return None
    version = blob[0]
    body = blob[1:]
    if version == _CODEC_VERSION_ZLIB_JSON:
        try:
            decoded = zlib.decompress(body).decode('utf-8')
            return json.loads(
                decoded,
                parse_constant=_reject_non_json_constant,
            )
        except (
            zlib.error,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            raise PayloadCorruptionError(
                "payload body is not valid zlib-compressed JSON"
            ) from exc
    raise UnsupportedPayloadVersionError(
        f"unknown payload codec version: {version!r}"
    )
