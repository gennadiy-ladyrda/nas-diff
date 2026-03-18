from __future__ import annotations

from pathlib import Path

from app.core.hashing import compute_file_hashes

def compute_dhash64_hex(file_path: Path) -> str:
    hash_bundle = compute_file_hashes(
        file_path,
        include_blake3_full=False,
        include_phash64=False,
    )
    assert hash_bundle.dhash64 is not None
    return hash_bundle.dhash64


def compute_phash64_hex(file_path: Path) -> str:
    hash_bundle = compute_file_hashes(
        file_path,
        include_blake3_full=False,
        include_dhash64=False,
    )
    assert hash_bundle.phash64 is not None
    return hash_bundle.phash64


def hamming_distance_hex(hash_hex_a: str, hash_hex_b: str) -> int:
    value_a = int(hash_hex_a, 16)
    value_b = int(hash_hex_b, 16)
    xor_value = value_a ^ value_b
    if hasattr(int, "bit_count"):
        return xor_value.bit_count()  # type: ignore[attr-defined]
    return bin(xor_value).count("1")
