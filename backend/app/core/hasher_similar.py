from __future__ import annotations

from pathlib import Path

_SIMILAR_HASH_BITS = 64


def compute_dhash64_hex(file_path: Path) -> str:
    data = file_path.read_bytes()
    if not data:
        return "0" * 16

    samples = _sample_bytes(data, _SIMILAR_HASH_BITS + 1)
    value = 0
    for idx in range(_SIMILAR_HASH_BITS):
        value <<= 1
        if samples[idx] > samples[idx + 1]:
            value |= 1
    return f"{value:016x}"


def compute_phash64_hex(file_path: Path) -> str:
    data = file_path.read_bytes()
    if not data:
        return "0" * 16

    samples = _sample_bytes(data, _SIMILAR_HASH_BITS)
    avg = sum(samples) / float(len(samples))
    value = 0
    for sample in samples:
        value <<= 1
        if sample >= avg:
            value |= 1
    return f"{value:016x}"


def hamming_distance_hex(hash_hex_a: str, hash_hex_b: str) -> int:
    value_a = int(hash_hex_a, 16)
    value_b = int(hash_hex_b, 16)
    xor_value = value_a ^ value_b
    if hasattr(int, "bit_count"):
        return xor_value.bit_count()  # type: ignore[attr-defined]
    return bin(xor_value).count("1")


def _sample_bytes(data: bytes, sample_count: int) -> list[int]:
    if len(data) == sample_count:
        return list(data)

    if len(data) > sample_count:
        step = len(data) / float(sample_count)
        return [data[min(int(idx * step), len(data) - 1)] for idx in range(sample_count)]

    padded = list(data)
    last_value = data[-1]
    while len(padded) < sample_count:
        padded.append(last_value)
    return padded
