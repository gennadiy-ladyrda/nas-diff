from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import File


class FileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        root_id: int,
        rel_path: str,
        abs_path: str,
        file_name: str,
        size_bytes: int,
        mtime_epoch_ns: int,
        extension: str | None = None,
        mime_type: str | None = None,
        ctime_epoch_ns: int | None = None,
        inode: int | None = None,
        dev: int | None = None,
        width: int | None = None,
        height: int | None = None,
        exif_datetime_original: str | None = None,
        exif_make: str | None = None,
        exif_model: str | None = None,
        first_seen_job_id: str | None = None,
        last_seen_job_id: str | None = None,
        is_present: int = 1,
    ) -> File:
        existing = self.get_by_abs_path(abs_path)

        if existing is None:
            file_obj = File(
                root_id=root_id,
                rel_path=rel_path,
                abs_path=abs_path,
                file_name=file_name,
                extension=extension,
                mime_type=mime_type,
                size_bytes=size_bytes,
                mtime_epoch_ns=mtime_epoch_ns,
                ctime_epoch_ns=ctime_epoch_ns,
                inode=inode,
                dev=dev,
                width=width,
                height=height,
                exif_datetime_original=exif_datetime_original,
                exif_make=exif_make,
                exif_model=exif_model,
                first_seen_job_id=first_seen_job_id,
                last_seen_job_id=last_seen_job_id,
                is_present=is_present,
            )
            self.session.add(file_obj)
        else:
            file_obj = existing
            file_obj.root_id = root_id
            file_obj.rel_path = rel_path
            file_obj.file_name = file_name
            file_obj.extension = extension
            file_obj.mime_type = mime_type
            file_obj.size_bytes = size_bytes
            file_obj.mtime_epoch_ns = mtime_epoch_ns
            file_obj.ctime_epoch_ns = ctime_epoch_ns
            file_obj.inode = inode
            file_obj.dev = dev
            file_obj.width = width
            file_obj.height = height
            file_obj.exif_datetime_original = exif_datetime_original
            file_obj.exif_make = exif_make
            file_obj.exif_model = exif_model
            if first_seen_job_id is not None and file_obj.first_seen_job_id is None:
                file_obj.first_seen_job_id = first_seen_job_id
            file_obj.last_seen_job_id = last_seen_job_id
            file_obj.is_present = is_present

        self.session.commit()
        self.session.refresh(file_obj)
        return file_obj

    def get(self, file_id: int) -> File | None:
        return self.session.get(File, file_id)

    def get_by_abs_path(self, abs_path: str) -> File | None:
        stmt = select(File).where(File.abs_path == abs_path)
        return self.session.scalar(stmt)

    def list_by_root(self, root_id: int, *, limit: int = 500, offset: int = 0) -> list[File]:
        stmt = (
            select(File)
            .where(File.root_id == root_id)
            .order_by(File.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt))

    def set_presence(self, file_id: int, *, is_present: int) -> File:
        file_obj = self._require(file_id)
        file_obj.is_present = is_present
        self.session.commit()
        self.session.refresh(file_obj)
        return file_obj

    def _require(self, file_id: int) -> File:
        file_obj = self.get(file_id)
        if file_obj is None:
            raise LookupError(f"file={file_id} not found")
        return file_obj
