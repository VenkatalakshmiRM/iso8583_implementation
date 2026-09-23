"""A small, ASCII ISO 8583:1987-style message codec used by the demo.

The wire format in this project is MTI (4 ASCII bytes), primary bitmap
(8 binary bytes), followed by fields in numeric order.  Variable-length
fields use ASCII length indicators, not BCD.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple


# field number: (human name, length type, length/fixed width)
FIELD_DICTIONARY = {
    2: ("Primary account number", "LLVAR", 19),
    3: ("Processing code", "FIXED", 6),
    4: ("Amount, transaction", "FIXED", 12),
    7: ("Transmission date and time", "FIXED", 10),
    11: ("Systems trace audit number", "FIXED", 6),
    12: ("Local transaction time", "FIXED", 6),
    13: ("Local transaction date", "FIXED", 4),
    32: ("Acquiring institution identification code", "LLVAR", 11),
    37: ("Retrieval reference number", "FIXED", 12),
    39: ("Response code", "FIXED", 2),
    41: ("Card acceptor terminal identification", "FIXED", 8),
    42: ("Card acceptor identification code", "FIXED", 15),
    49: ("Currency code", "FIXED", 3),
    52: ("PIN block (demo: four ASCII digits)", "FIXED", 4),
    62: ("Private use", "LLLVAR", 999),
}


def encode_primary_bitmap(present_fields: Iterable[int]) -> bytes:
    """Encode fields 2..64 into an eight-byte ISO 8583 primary bitmap."""
    bitmap = bytearray(8)
    for field in present_fields:
        if not isinstance(field, int) or not 2 <= field <= 64:
            raise ValueError("only primary-bitmap fields 2 through 64 are supported")
        bit_index = field - 1
        bitmap[bit_index // 8] |= 0x80 >> (bit_index % 8)
    return bytes(bitmap)


def decode_primary_bitmap(bitmap: bytes) -> list[int]:
    """Return the field numbers represented by an eight-byte bitmap."""
    if len(bitmap) != 8:
        raise ValueError("primary bitmap must be exactly 8 bytes")
    if bitmap[0] & 0x80:
        raise ValueError("secondary bitmaps are not supported by this demo")
    return [field for field in range(2, 65)
            if bitmap[(field - 1) // 8] & (0x80 >> ((field - 1) % 8))]


def _ascii(value: object, field: int) -> bytes:
    try:
        return str(value).encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"DE{field} must contain ASCII data") from exc


def pack_message(mti: str, data_elements_dict: Dict[int, object]) -> bytes:
    """Pack an MTI and supported data elements into an ISO 8583 byte stream."""
    if not isinstance(mti, str) or len(mti) != 4 or not mti.isdigit():
        raise ValueError("MTI must be a four-digit string")
    unknown = set(data_elements_dict) - set(FIELD_DICTIONARY)
    if unknown:
        raise ValueError(f"unsupported data element(s): {sorted(unknown)}")
    fields = sorted(data_elements_dict)
    body = bytearray(mti.encode("ascii")) + encode_primary_bitmap(fields)
    for field in fields:
        _name, kind, limit = FIELD_DICTIONARY[field]
        value = _ascii(data_elements_dict[field], field)
        if kind == "FIXED":
            if len(value) != limit:
                raise ValueError(f"DE{field} must be exactly {limit} bytes")
        elif kind == "LLVAR":
            if len(value) > limit or len(value) > 99:
                raise ValueError(f"DE{field} exceeds LLVAR limit of {limit}")
            body.extend(f"{len(value):02d}".encode("ascii"))
        elif kind == "LLLVAR":
            if len(value) > limit:
                raise ValueError(f"DE{field} exceeds LLLVAR limit of {limit}")
            body.extend(f"{len(value):03d}".encode("ascii"))
        body.extend(value)
    return bytes(body)


def unpack_message(raw_bytes: bytes) -> Tuple[str, Dict[int, str]]:
    """Decode one unframed ISO 8583 message and reject malformed/trailing data."""
    if len(raw_bytes) < 12:
        raise ValueError("message is shorter than MTI plus primary bitmap")
    try:
        mti = raw_bytes[:4].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("MTI is not ASCII") from exc
    if not mti.isdigit():
        raise ValueError("MTI must be four digits")
    fields = decode_primary_bitmap(raw_bytes[4:12])
    offset, decoded = 12, {}
    for field in fields:
        _name, kind, size = FIELD_DICTIONARY.get(field, (None, None, None))
        if kind is None:
            raise ValueError(f"DE{field} appears in bitmap but has no dictionary entry")
        if kind == "FIXED":
            length = size
        else:
            width = 2 if kind == "LLVAR" else 3
            if offset + width > len(raw_bytes):
                raise ValueError(f"truncated length indicator for DE{field}")
            prefix = raw_bytes[offset:offset + width]
            if not prefix.isdigit():
                raise ValueError(f"non-numeric length indicator for DE{field}")
            length = int(prefix)
            offset += width
            if length > size:
                raise ValueError(f"DE{field} length exceeds dictionary limit")
        if offset + length > len(raw_bytes):
            raise ValueError(f"truncated value for DE{field}")
        try:
            decoded[field] = raw_bytes[offset:offset + length].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError(f"DE{field} is not ASCII") from exc
        offset += length
    if offset != len(raw_bytes):
        raise ValueError("unexpected trailing bytes after ISO 8583 fields")
    return mti, decoded


def hexdump(raw: bytes, width: int = 16) -> str:
    """Print and return a conventional offset / hexadecimal / ASCII dump."""
    lines = []
    for offset in range(0, len(raw), width):
        chunk = raw[offset:offset + width]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk).ljust(width * 3 - 1)
        ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        lines.append(f"{offset:04X}  {hex_part}  |{ascii_part}|")
    result = "\n".join(lines)
    print(result)
    return result
