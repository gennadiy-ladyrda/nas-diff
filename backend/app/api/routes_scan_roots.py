from __future__ import annotations

import posixpath

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.db.models import ScanRoot
from app.db.repositories import (
    ScanRootAlreadyExistsError,
    ScanRootInUseError,
    ScanRootRepository,
)

router = APIRouter(prefix="/scan/roots", tags=["scan_roots"])

_NAS_MOUNT_ROOT = "/nas"


class ScanRootCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class ScanRootUpdateRequest(BaseModel):
    enabled: bool


class ScanRootResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    enabled: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[ScanRootResponse])
def list_scan_roots(db: Session = Depends(get_db_session)) -> list[ScanRoot]:
    repo = ScanRootRepository(db)
    return repo.list_all()


@router.post("", response_model=ScanRootResponse, status_code=status.HTTP_201_CREATED)
def create_scan_root(
    payload: ScanRootCreateRequest,
    db: Session = Depends(get_db_session),
) -> ScanRoot:
    repo = ScanRootRepository(db)

    try:
        canonical_path = _canonicalize_scan_root_path(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        return repo.create(path=canonical_path, enabled=1)
    except ScanRootAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"scan root '{canonical_path}' already exists",
        ) from exc


@router.patch("/{root_id}", response_model=ScanRootResponse)
def update_scan_root(
    payload: ScanRootUpdateRequest,
    root_id: int = Path(..., ge=1),
    db: Session = Depends(get_db_session),
) -> ScanRoot:
    repo = ScanRootRepository(db)
    try:
        return repo.set_enabled(root_id, enabled=int(payload.enabled))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{root_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan_root(
    root_id: int = Path(..., ge=1),
    db: Session = Depends(get_db_session),
) -> Response:
    repo = ScanRootRepository(db)
    try:
        repo.delete(root_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScanRootInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _canonicalize_scan_root_path(path: str) -> str:
    if not path.strip():
        raise ValueError("path must not be empty")

    canonical = posixpath.normpath(path.strip())

    if not canonical.startswith("/"):
        raise ValueError("path must be absolute")

    mount_root = posixpath.normpath(_NAS_MOUNT_ROOT)
    if posixpath.commonpath([mount_root, canonical]) != mount_root:
        raise ValueError(f"path must be under '{_NAS_MOUNT_ROOT}'")

    return canonical
