"""Minimal bencode codec, used to normalise downloaded .torrent files."""

from __future__ import annotations

from typing import Any

BencodeValue = int | bytes | list | dict


class BencodeError(ValueError):
    """The data is not valid bencode."""


def _decode_int(data: bytes, position: int) -> tuple[int, int]:
    end = data.index(b"e", position)
    return int(data[position + 1 : end]), end + 1


def _decode_bytes(data: bytes, position: int) -> tuple[bytes, int]:
    colon = data.index(b":", position)
    length = int(data[position:colon])
    start = colon + 1
    if start + length > len(data):
        raise BencodeError("string exceeds the data")
    return data[start : start + length], start + length


def _decode_list(data: bytes, position: int) -> tuple[list, int]:
    items = []
    position += 1
    while data[position : position + 1] != b"e":
        item, position = _decode_at(data, position)
        items.append(item)
    return items, position + 1


def _decode_dict(data: bytes, position: int) -> tuple[dict, int]:
    result = {}
    position += 1
    while data[position : position + 1] != b"e":
        key, position = _decode_bytes(data, position)
        result[key], position = _decode_at(data, position)
    return result, position + 1


def _decode_at(data: bytes, position: int) -> tuple[Any, int]:
    marker = data[position : position + 1]
    if marker == b"i":
        return _decode_int(data, position)
    if marker == b"l":
        return _decode_list(data, position)
    if marker == b"d":
        return _decode_dict(data, position)
    if marker.isdigit():
        return _decode_bytes(data, position)
    raise BencodeError(f"unexpected byte at {position}")


def decode(data: bytes) -> BencodeValue:
    try:
        value, end = _decode_at(data, 0)
    except (ValueError, IndexError) as error:
        raise BencodeError(str(error)) from error
    if end != len(data):
        raise BencodeError("trailing data")
    return value


def encode(value: Any) -> bytes:
    """Encode with dictionary keys sorted, as the specification requires."""
    if isinstance(value, bool):
        raise BencodeError("booleans are not supported")
    if isinstance(value, int):
        return b"i%de" % value
    if isinstance(value, bytes):
        return b"%d:%s" % (len(value), value)
    if isinstance(value, list):
        return b"l" + b"".join(encode(item) for item in value) + b"e"
    if isinstance(value, dict):
        body = b"".join(
            encode(key) + encode(value[key]) for key in sorted(value)
        )
        return b"d" + body + b"e"
    raise BencodeError(f"cannot encode {type(value).__name__}")


def normalize(data: bytes) -> bytes:
    """Re-encode a torrent so dictionary keys are sorted (Sonarr needs it)."""
    return encode(decode(data))
