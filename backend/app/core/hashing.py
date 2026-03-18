from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CHUNK_SIZE = 1024 * 1024
_SIMILAR_HASH_BITS = 64


@dataclass(frozen=True)
class ComputedFileHashes:
    blake3_full: str | None = None
    dhash64: str | None = None
    phash64: str | None = None


def compute_file_hashes(
    file_path: Path,
    *,
    size_bytes: int | None = None,
    include_blake3_full: bool = True,
    include_dhash64: bool = True,
    include_phash64: bool = True,
) -> ComputedFileHashes:
    if not any((include_blake3_full, include_dhash64, include_phash64)):
        raise ValueError("at least one hash must be requested")

    resolved_size = file_path.stat().st_size if size_bytes is None else size_bytes
    exact_hasher = _build_content_hasher() if include_blake3_full else None
    dhash_sampler = _ByteSampler(resolved_size, _SIMILAR_HASH_BITS + 1) if include_dhash64 else None
    phash_sampler = _ByteSampler(resolved_size, _SIMILAR_HASH_BITS) if include_phash64 else None

    with file_path.open("rb") as fh:
        offset = 0
        while True:
            chunk = fh.read(_CHUNK_SIZE)
            if not chunk:
                break

            if exact_hasher is not None:
                exact_hasher.update(chunk)
            if dhash_sampler is not None:
                dhash_sampler.consume(offset, chunk)
            if phash_sampler is not None:
                phash_sampler.consume(offset, chunk)
            offset += len(chunk)

    return ComputedFileHashes(
        blake3_full=exact_hasher.hexdigest() if exact_hasher is not None else None,
        dhash64=_compute_dhash64_hex(dhash_sampler.finish()) if dhash_sampler is not None else None,
        phash64=_compute_phash64_hex(phash_sampler.finish()) if phash_sampler is not None else None,
    )


def _build_content_hasher() -> Any:
    try:
        import blake3  # type: ignore[import-not-found]

        return blake3.blake3()
    except Exception:
        return hashlib.sha256()


class _ByteSampler:
    def __init__(self, file_size: int, sample_count: int) -> None:
        self._file_size = file_size
        self._sample_count = sample_count
        if file_size <= sample_count:
            self._buffer = bytearray()
            self._positions: list[int] | None = None
            self._samples: list[int] | None = None
        else:
            self._buffer = None
            self._positions = _build_sample_positions(file_size, sample_count)
            self._samples = [0] * sample_count
        self._next_index = 0

    def consume(self, offset: int, chunk: bytes) -> None:
        if self._file_size == 0:
            return

        if self._buffer is not None:
            self._buffer.extend(chunk)
            return

        assert self._positions is not None
        assert self._samples is not None
        chunk_end = offset + len(chunk)

        while self._next_index < self._sample_count:
            sample_position = self._positions[self._next_index]
            if sample_position >= chunk_end:
                return

            self._samples[self._next_index] = chunk[sample_position - offset]
            self._next_index += 1

    def finish(self) -> list[int]:
        if self._file_size == 0:
            return []
        if self._buffer is not None:
            return _sample_bytes(bytes(self._buffer), self._sample_count)
        assert self._samples is not None
        return self._samples


def _build_sample_positions(file_size: int, sample_count: int) -> list[int]:
    step = file_size / float(sample_count)
    return [min(int(index * step), file_size - 1) for index in range(sample_count)]


def _compute_dhash64_hex(samples: list[int]) -> str:
    if not samples:
        return "0" * 16

    value = 0
    for index in range(_SIMILAR_HASH_BITS):
        value <<= 1
        if samples[index] > samples[index + 1]:
            value |= 1
    return f"{value:016x}"


def _compute_phash64_hex(samples: list[int]) -> str:
    if not samples:
        return "0" * 16

    avg = sum(samples) / float(len(samples))
    value = 0
    for sample in samples:
        value <<= 1
        if sample >= avg:
            value |= 1
    return f"{value:016x}"


def _sample_bytes(data: bytes, sample_count: int) -> list[int]:
    if len(data) == sample_count:
        return list(data)

    if len(data) > sample_count:
        step = len(data) / float(sample_count)
        return [data[min(int(index * step), len(data) - 1)] for index in range(sample_count)]

    padded = list(data)
    last_value = data[-1]
    while len(padded) < sample_count:
        padded.append(last_value)
    return padded
