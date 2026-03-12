from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ScanRoot


class ScanRootAlreadyExistsError(RuntimeError):
    """Raised when a scan root with the same canonical path already exists."""


class ScanRootInUseError(RuntimeError):
    """Raised when scan root cannot be deleted due to existing references."""


class ScanRootRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, path: str, enabled: int = 1) -> ScanRoot:
        root = ScanRoot(path=path, enabled=enabled, updated_at=_utc_iso_now())
        self.session.add(root)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if _is_unique_path_error(exc):
                raise ScanRootAlreadyExistsError(path) from exc
            raise

        self.session.refresh(root)
        return root

    def get(self, root_id: int) -> ScanRoot | None:
        return self.session.get(ScanRoot, root_id)

    def list_all(self, *, enabled: bool | None = None) -> list[ScanRoot]:
        stmt = select(ScanRoot).order_by(ScanRoot.id.asc())
        if enabled is not None:
            stmt = stmt.where(ScanRoot.enabled == int(enabled))
        return list(self.session.scalars(stmt))

    def set_enabled(self, root_id: int, *, enabled: int) -> ScanRoot:
        root = self._require(root_id)
        root.enabled = enabled
        root.updated_at = _utc_iso_now()
        self.session.commit()
        self.session.refresh(root)
        return root

    def delete(self, root_id: int) -> None:
        root = self._require(root_id)
        self.session.delete(root)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ScanRootInUseError(
                f"scan_root={root_id} is referenced by existing scan jobs"
            ) from exc

    def _require(self, root_id: int) -> ScanRoot:
        root = self.get(root_id)
        if root is None:
            raise LookupError(f"scan_root={root_id} not found")
        return root


def _is_unique_path_error(error: IntegrityError) -> bool:
    return "unique constraint failed: scan_roots.path" in str(error).lower()


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
