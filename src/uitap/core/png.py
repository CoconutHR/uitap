"""Standard-library PNG helpers shared by screenshots, Inspector and tests."""
from __future__ import annotations

import math
import struct
import zlib

from ..errors import DeviceResponseError


_MAX_CROPPABLE_PNG_BYTES = 64 * 1024 * 1024
"""Upper bound for a decoded PNG frame handled by the standard-library cropper."""

def png_size(image: bytes) -> tuple[float, float] | None:
    """Return PNG dimensions without adding an image-library dependency."""
    if len(image) < 24 or not image.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width = int.from_bytes(image[16:20], "big")
    height = int.from_bytes(image[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return float(width), float(height)

def crop_png(image: bytes, left: int, top: int, right: int, bottom: int) -> bytes:
    """Crop a standard screenshot PNG using a physical-pixel rectangle.

    The rectangle follows the public coordinate contract: left/top are
    inclusive, right/bottom are exclusive. This standard-library helper is
    also used by Inspector so a frozen source PNG can be cropped without
    requiring Pillow or round-tripping through a browser canvas.
    """
    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DeviceResponseError("screenshot is not a PNG image")
    size = png_size(image)
    if size is None:
        raise DeviceResponseError("PNG image has no valid dimensions")
    width, height = (int(size[0]), int(size[1]))
    values = (left, top, right, bottom)
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values) or not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("crop pixels must satisfy screen bounds and left < right, top < bottom")
    offset, ihdr, compressed = 8, None, bytearray()
    while offset + 12 <= len(image):
        length = int.from_bytes(image[offset:offset + 4], "big")
        kind, data = image[offset + 4:offset + 8], image[offset + 8:offset + 8 + length]
        if len(data) != length:
            raise DeviceResponseError("truncated PNG image")
        if kind == b"IHDR": ihdr = data
        elif kind == b"IDAT": compressed.extend(data)
        elif kind == b"IEND": break
        offset += length + 12
    if ihdr is None or len(ihdr) != 13:
        raise DeviceResponseError("PNG image has no valid IHDR chunk")
    width, height, depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    channels = {2: 3, 6: 4}.get(color_type)
    if depth != 8 or channels is None or compression != 0 or filter_method != 0 or interlace != 0:
        raise DeviceResponseError("only non-interlaced 8-bit RGB/RGBA PNG screenshots can be cropped")
    stride, bpp = width * channels, channels
    expected_raw_length = height * (stride + 1)
    if expected_raw_length > _MAX_CROPPABLE_PNG_BYTES:
        raise DeviceResponseError("PNG image exceeds the maximum supported crop size")
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(bytes(compressed), expected_raw_length + 1)
        if len(raw) > expected_raw_length or decompressor.unconsumed_tail:
            raise DeviceResponseError("PNG image data exceeds the expected size")
        raw += decompressor.flush()
    except zlib.error as exc:
        raise DeviceResponseError("PNG image data cannot be decompressed") from exc
    if len(raw) != expected_raw_length or not decompressor.eof:
        raise DeviceResponseError("PNG image data has an invalid length")
    rows: list[bytearray] = []
    previous = bytearray(stride)
    for row_index in range(height):
        start = row_index * (stride + 1); filter_type = raw[start]; row = bytearray(raw[start + 1:start + 1 + stride])
        for index in range(stride):
            a = row[index - bpp] if index >= bpp else 0; b = previous[index]; c = previous[index - bpp] if index >= bpp else 0
            if filter_type == 1: row[index] = (row[index] + a) & 255
            elif filter_type == 2: row[index] = (row[index] + b) & 255
            elif filter_type == 3: row[index] = (row[index] + ((a + b) // 2)) & 255
            elif filter_type == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[index] = (row[index] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            elif filter_type != 0: raise DeviceResponseError("PNG image uses an unsupported filter")
        rows.append(row); previous = row
    cropped_width, cropped_height = right - left, bottom - top
    cropped = b"".join(b"\0" + bytes(row[left * channels:right * channels]) for row in rows[top:bottom])
    header = struct.pack(">IIBBBBB", cropped_width, cropped_height, depth, color_type, compression, filter_method, interlace)
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(cropped)) + chunk(b"IEND", b"")

def crop_png_relative(image: bytes, left: float, top: float, right: float, bottom: float) -> bytes:
    """Crop a standard screenshot PNG using a 0..1 relative rectangle."""
    try:
        left, top, right, bottom = (float(value) for value in (left, top, right, bottom))
    except (TypeError, ValueError) as exc:
        raise ValueError("crop ratios must be finite numbers between 0 and 1") from exc
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in (left, top, right, bottom)) or left >= right or top >= bottom:
        raise ValueError("crop ratios must satisfy 0 <= left < right <= 1 and 0 <= top < bottom <= 1")
    size = png_size(image)
    if size is None:
        raise DeviceResponseError("screenshot is not a PNG image")
    width, height = (int(size[0]), int(size[1]))
    x0, x1 = int(width * left), min(width, max(int(width * right), int(width * left) + 1))
    y0, y1 = int(height * top), min(height, max(int(height * bottom), int(height * top) + 1))
    return crop_png(image, x0, y0, x1, y1)
