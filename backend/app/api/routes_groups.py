from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.db.models import ExactGroupItem, File, SimilarGroupItem
from app.db.repositories import UserDecisionRepository
from app.services.decision_service import DecisionService

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupDecisionRequest(BaseModel):
    file_id: int = Field(ge=1)
    decision: Literal["keep", "trash", "delete", "ignore"]
    note: Optional[str] = Field(default=None, max_length=512)


class GroupDecisionResponse(BaseModel):
    group_kind: Literal["exact", "similar"]
    group_id: int
    file_id: int
    decision: str
    note: Optional[str]


@router.get("/{group_kind}/{group_id}")
def get_group_details(
    group_kind: Literal["exact", "similar"],
    group_id: int = Path(..., ge=1),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    if group_kind == "exact":
        rows = db.execute(
            select(
                ExactGroupItem.file_id,
                ExactGroupItem.is_primary,
                ExactGroupItem.keep_score,
                ExactGroupItem.reason,
                File.abs_path,
                File.size_bytes,
            )
            .join(File, File.id == ExactGroupItem.file_id)
            .where(ExactGroupItem.group_id == group_id)
            .order_by(ExactGroupItem.file_id.asc())
        ).all()
    else:
        rows = db.execute(
            select(
                SimilarGroupItem.file_id,
                SimilarGroupItem.is_primary,
                SimilarGroupItem.keep_score,
                SimilarGroupItem.reason,
                SimilarGroupItem.distance_to_anchor,
                SimilarGroupItem.confidence,
                File.abs_path,
                File.size_bytes,
            )
            .join(File, File.id == SimilarGroupItem.file_id)
            .where(SimilarGroupItem.group_id == group_id)
            .order_by(SimilarGroupItem.file_id.asc())
        ).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"group not found: kind={group_kind} group_id={group_id}",
        )

    decisions = UserDecisionRepository(db).list_for_group(group_kind=group_kind, group_id=group_id)
    decisions_map = {decision.file_id: decision.decision for decision in decisions}

    items = []
    if group_kind == "exact":
        for file_id, is_primary, keep_score, reason, abs_path, size_bytes in rows:
            items.append(
                {
                    "file_id": int(file_id),
                    "abs_path": abs_path,
                    "size_bytes": int(size_bytes),
                    "is_primary": bool(is_primary),
                    "keep_score": keep_score,
                    "reason": reason,
                    "decision": decisions_map.get(int(file_id)),
                }
            )
    else:
        for file_id, is_primary, keep_score, reason, distance, confidence, abs_path, size_bytes in rows:
            items.append(
                {
                    "file_id": int(file_id),
                    "abs_path": abs_path,
                    "size_bytes": int(size_bytes),
                    "is_primary": bool(is_primary),
                    "keep_score": keep_score,
                    "reason": reason,
                    "distance_to_anchor": int(distance),
                    "confidence": confidence,
                    "decision": decisions_map.get(int(file_id)),
                }
            )

    return {
        "group_kind": group_kind,
        "group_id": group_id,
        "items": items,
    }


@router.post("/{group_kind}/{group_id}/decision", response_model=GroupDecisionResponse)
def save_group_decision(
    payload: GroupDecisionRequest,
    group_kind: Literal["exact", "similar"],
    group_id: int = Path(..., ge=1),
    db: Session = Depends(get_db_session),
) -> GroupDecisionResponse:
    service = DecisionService(db)
    try:
        row = service.save_group_decision(
            group_kind=group_kind,
            group_id=group_id,
            file_id=payload.file_id,
            decision=payload.decision,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GroupDecisionResponse(
        group_kind=group_kind,
        group_id=group_id,
        file_id=row.file_id,
        decision=row.decision,
        note=row.note,
    )
