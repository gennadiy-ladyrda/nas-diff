"""Core business logic package."""

from app.core.dedup_exact import ExactDedupResult, build_exact_groups
from app.core.dedup_similar import SimilarDedupResult, build_similar_groups
from app.core.decision_engine import DecisionRecomputeResult, apply_auto_primary_scoring
from app.core.scanner import ScanIndexingResult, scan_and_index

__all__ = [
    "DecisionRecomputeResult",
    "ExactDedupResult",
    "ScanIndexingResult",
    "SimilarDedupResult",
    "apply_auto_primary_scoring",
    "build_exact_groups",
    "build_similar_groups",
    "scan_and_index",
]
