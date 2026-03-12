from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import ExactGroup, ExactGroupItem, File, SimilarGroup, SimilarGroupItem


@dataclass(frozen=True)
class DecisionRecomputeResult:
    exact_groups_updated: int
    similar_groups_updated: int


def apply_auto_primary_scoring(session: Session, *, job_id: str) -> DecisionRecomputeResult:
    exact_groups = _apply_exact_group_scoring(session, job_id=job_id)
    similar_groups = _apply_similar_group_scoring(session, job_id=job_id)
    return DecisionRecomputeResult(
        exact_groups_updated=exact_groups,
        similar_groups_updated=similar_groups,
    )


def _apply_exact_group_scoring(session: Session, *, job_id: str) -> int:
    group_ids = list(
        session.scalars(
            select(ExactGroup.id).where(ExactGroup.job_id == job_id).order_by(ExactGroup.id.asc())
        )
    )
    for group_id in group_ids:
        rows = session.execute(
            select(
                ExactGroupItem.file_id,
                File.width,
                File.height,
                File.size_bytes,
                File.exif_datetime_original,
                File.mtime_epoch_ns,
            )
            .join(File, File.id == ExactGroupItem.file_id)
            .where(ExactGroupItem.group_id == group_id)
            .order_by(ExactGroupItem.file_id.asc())
        ).all()
        _apply_scores_to_exact_items(session, group_id=group_id, rows=rows)
    session.commit()
    return len(group_ids)


def _apply_scores_to_exact_items(session: Session, *, group_id: int, rows) -> None:  # type: ignore[no-untyped-def]
    if not rows:
        return

    scores = _calculate_scores(rows)
    winner = max(scores, key=lambda payload: (payload.score, -payload.file_id))
    for payload in scores:
        session.execute(
            update(ExactGroupItem)
            .where(ExactGroupItem.group_id == group_id, ExactGroupItem.file_id == payload.file_id)
            .values(
                keep_score=payload.score,
                reason=payload.reason,
                is_primary=1 if payload.file_id == winner.file_id else 0,
            )
        )


def _apply_similar_group_scoring(session: Session, *, job_id: str) -> int:
    group_ids = list(
        session.scalars(
            select(SimilarGroup.id).where(SimilarGroup.job_id == job_id).order_by(SimilarGroup.id.asc())
        )
    )
    for group_id in group_ids:
        rows = session.execute(
            select(
                SimilarGroupItem.file_id,
                File.width,
                File.height,
                File.size_bytes,
                File.exif_datetime_original,
                File.mtime_epoch_ns,
            )
            .join(File, File.id == SimilarGroupItem.file_id)
            .where(SimilarGroupItem.group_id == group_id)
            .order_by(SimilarGroupItem.file_id.asc())
        ).all()
        _apply_scores_to_similar_items(session, group_id=group_id, rows=rows)
    session.commit()
    return len(group_ids)


def _apply_scores_to_similar_items(session: Session, *, group_id: int, rows) -> None:  # type: ignore[no-untyped-def]
    if not rows:
        return

    scores = _calculate_scores(rows)
    winner = max(scores, key=lambda payload: (payload.score, -payload.file_id))
    for payload in scores:
        session.execute(
            update(SimilarGroupItem)
            .where(SimilarGroupItem.group_id == group_id, SimilarGroupItem.file_id == payload.file_id)
            .values(
                keep_score=payload.score,
                reason=payload.reason,
                is_primary=1 if payload.file_id == winner.file_id else 0,
            )
        )


@dataclass(frozen=True)
class _FileScore:
    file_id: int
    score: float
    reason: str


def _calculate_scores(rows) -> list[_FileScore]:  # type: ignore[no-untyped-def]
    max_resolution = max((int(width or 0) * int(height or 0)) for _, width, height, *_rest in rows)
    max_size = max(int(size_bytes) for _, _w, _h, size_bytes, *_rest in rows)
    min_mtime = min(int(mtime_epoch_ns) for *_lead, mtime_epoch_ns in rows)

    result: list[_FileScore] = []
    for file_id, width, height, size_bytes, exif_datetime_original, mtime_epoch_ns in rows:
        score = 0.0
        reasons: list[str] = []

        resolution = int(width or 0) * int(height or 0)
        if resolution > 0 and resolution == max_resolution:
            score += 5.0
            reasons.append("max_resolution")
        if int(size_bytes) == max_size:
            score += 3.0
            reasons.append("max_size")
        if exif_datetime_original:
            score += 2.0
            reasons.append("has_exif_datetime")
        if int(mtime_epoch_ns) == min_mtime:
            score += 1.0
            reasons.append("earliest_mtime")

        result.append(
            _FileScore(
                file_id=int(file_id),
                score=score,
                reason=",".join(reasons) if reasons else "fallback_lowest_file_id",
            )
        )
    return result
