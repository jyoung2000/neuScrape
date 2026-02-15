"""Lightweight perceptual hashing using only Pillow (no scipy/numpy)."""

from PIL import Image


class ImageHash:
    """Perceptual hash value with Hamming-distance comparison."""

    __slots__ = ("_value", "_hex")

    def __init__(self, value: int, hex_str: str):
        self._value = value
        self._hex = hex_str

    def __str__(self) -> str:
        return self._hex

    def __sub__(self, other: "ImageHash") -> int:
        """Hamming distance between two hashes."""
        return bin(self._value ^ other._value).count("1")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ImageHash):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return self._value


def phash(image: Image.Image, hash_size: int = 8) -> ImageHash:
    """Compute a difference-hash (dHash) as a drop-in replacement for imagehash.phash.

    Uses horizontal-gradient comparison — fast, effective for deduplication,
    and needs nothing beyond Pillow.
    """
    resized = image.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(resized.getdata())

    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            if pixels[idx] < pixels[idx + 1]:
                bits |= 1 << (row * hash_size + col)

    hex_str = format(bits, f"0{hash_size * hash_size // 4}x")
    return ImageHash(bits, hex_str)


def hex_to_hash(hex_str: str) -> ImageHash:
    """Reconstruct an ImageHash from its hex string."""
    value = int(hex_str, 16)
    return ImageHash(value, hex_str)
