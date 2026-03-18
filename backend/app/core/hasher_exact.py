from __future__ import annotations

from pathlib import Path

from app.core.hashing import compute_file_hashes


def compute_blake3_full_hex(file_path: Path) -> str:
    """
    Compute full-file content hash.

    The project contract uses `blake3_full` hash type in DB.
    If `blake3` package is unavailable, fallback to `sha256` while keeping the same hash slot.
    """
    hash_bundle = compute_file_hashes(
        file_path,
        include_dhash64=False,
        include_phash64=False,
    )
    assert hash_bundle.blake3_full is not None
    return hash_bundle.blake3_full
