from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import FileHash


class FileHashRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, *, file_id: int, hash_type: str, hash_hex: str) -> FileHash:
        existing = self.get(file_id=file_id, hash_type=hash_type)
        if existing is None:
            file_hash = FileHash(file_id=file_id, hash_type=hash_type, hash_hex=hash_hex)
            self.session.add(file_hash)
        else:
            file_hash = existing
            file_hash.hash_hex = hash_hex

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(file_hash)
        return file_hash

    def get(self, *, file_id: int, hash_type: str) -> FileHash | None:
        stmt = select(FileHash).where(FileHash.file_id == file_id, FileHash.hash_type == hash_type)
        return self.session.scalar(stmt)

    def list_for_file(self, *, file_id: int) -> list[FileHash]:
        stmt = (
            select(FileHash)
            .where(FileHash.file_id == file_id)
            .order_by(FileHash.hash_type.asc())
        )
        return list(self.session.scalars(stmt))
