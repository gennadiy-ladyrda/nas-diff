from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def compute_blake3_full_hex(file_path: Path) -> str:
    """
    Compute full-file content hash.

    The project contract uses `blake3_full` hash type in DB.
    If `blake3` package is unavailable, fallback to `sha256` while keeping the same hash slot.
    """
    try:
        import blake3  # type: ignore[import-not-found]

        hasher = blake3.blake3()
    except Exception:
        hasher = hashlib.sha256()

    with file_path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()
