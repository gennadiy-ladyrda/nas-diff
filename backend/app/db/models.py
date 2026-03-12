from __future__ import annotations

from typing import Optional

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ScanRoot(Base):
    __tablename__ = "scan_roots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))

    files: Mapped[list[File]] = relationship(back_populates="scan_root")


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        CheckConstraint("mode IN ('exact', 'similar', 'both')", name="chk_scan_jobs_mode"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'canceled')",
            name="chk_scan_jobs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))
    started_at: Mapped[Optional[str]] = mapped_column(Text)
    finished_at: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    files_indexed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    exact_groups_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    similar_groups_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    reclaimable_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class ScanJobRoot(Base):
    __tablename__ = "scan_job_roots"

    job_id: Mapped[str] = mapped_column(
        ForeignKey("scan_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    root_id: Mapped[int] = mapped_column(
        ForeignKey("scan_roots.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        Index("idx_files_root_rel_path", "root_id", "rel_path"),
        Index("idx_files_size", "size_bytes"),
        Index("idx_files_mtime", "mtime_epoch_ns"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_id: Mapped[int] = mapped_column(ForeignKey("scan_roots.id", ondelete="RESTRICT"), nullable=False)
    rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    abs_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[Optional[str]] = mapped_column(Text)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mtime_epoch_ns: Mapped[int] = mapped_column(Integer, nullable=False)
    ctime_epoch_ns: Mapped[Optional[int]] = mapped_column(Integer)
    inode: Mapped[Optional[int]] = mapped_column(Integer)
    dev: Mapped[Optional[int]] = mapped_column(Integer)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    exif_datetime_original: Mapped[Optional[str]] = mapped_column(Text)
    exif_make: Mapped[Optional[str]] = mapped_column(Text)
    exif_model: Mapped[Optional[str]] = mapped_column(Text)
    first_seen_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("scan_jobs.id", ondelete="SET NULL"))
    last_seen_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("scan_jobs.id", ondelete="SET NULL"))
    is_present: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))
    updated_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))

    scan_root: Mapped[ScanRoot] = relationship(back_populates="files")


class FileHash(Base):
    __tablename__ = "file_hashes"
    __table_args__ = (
        UniqueConstraint("file_id", "hash_type", name="uq_file_hashes_file_hash_type"),
        Index("idx_file_hashes_lookup", "hash_type", "hash_hex"),
        CheckConstraint(
            "hash_type IN ('blake3_full', 'dhash64', 'phash64')",
            name="chk_file_hashes_hash_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    hash_type: Mapped[str] = mapped_column(String, nullable=False)
    hash_hex: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))


class ExactGroup(Base):
    __tablename__ = "exact_groups"
    __table_args__ = (
        UniqueConstraint("job_id", "signature", name="uq_exact_groups_job_signature"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    reclaimable_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))

    items: Mapped[list[ExactGroupItem]] = relationship(back_populates="group", cascade="all, delete-orphan")


class ExactGroupItem(Base):
    __tablename__ = "exact_group_items"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("exact_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    keep_score: Mapped[Optional[float]] = mapped_column(Float)
    reason: Mapped[Optional[str]] = mapped_column(Text)

    group: Mapped[ExactGroup] = relationship(back_populates="items")


class SimilarGroup(Base):
    __tablename__ = "similar_groups"
    __table_args__ = (
        CheckConstraint(
            "algorithm IN ('phash64', 'dhash64', 'hybrid')",
            name="chk_similar_groups_algorithm",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id", ondelete="CASCADE"), nullable=False)
    algorithm: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))

    items: Mapped[list[SimilarGroupItem]] = relationship(back_populates="group", cascade="all, delete-orphan")


class SimilarGroupItem(Base):
    __tablename__ = "similar_group_items"
    __table_args__ = (
        Index("idx_similar_group_items_distance", "group_id", "distance_to_anchor"),
    )

    group_id: Mapped[int] = mapped_column(
        ForeignKey("similar_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    distance_to_anchor: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    keep_score: Mapped[Optional[float]] = mapped_column(Float)
    reason: Mapped[Optional[str]] = mapped_column(Text)

    group: Mapped[SimilarGroup] = relationship(back_populates="items")


class UserDecision(Base):
    __tablename__ = "user_decisions"
    __table_args__ = (
        UniqueConstraint("group_kind", "group_id", "file_id", name="uq_user_decisions_group_file"),
        Index("idx_user_decisions_lookup", "group_kind", "group_id", "decision"),
        CheckConstraint("group_kind IN ('exact', 'similar')", name="chk_user_decisions_group_kind"),
        CheckConstraint("decision IN ('keep', 'trash', 'delete', 'ignore')", name="chk_user_decisions_decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_kind: Mapped[str] = mapped_column(String, nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))


class ActionBatch(Base):
    __tablename__ = "action_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'executed', 'partially_failed', 'failed', 'rolled_back')",
            name="chk_action_batches_status",
        ),
        CheckConstraint(
            "action_type IN ('move_to_trash', 'delete_permanent', 'restore')",
            name="chk_action_batches_action_type",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    requested_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))
    confirmed_at: Mapped[Optional[str]] = mapped_column(Text)
    executed_at: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'local_admin'"))
    dry_run: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    summary: Mapped[Optional[str]] = mapped_column(Text)

    items: Mapped[list[ActionItem]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "file_id", name="uq_action_items_batch_file"),
        Index("idx_action_items_batch_status", "batch_id", "status"),
        CheckConstraint(
            "status IN ('pending', 'done', 'failed', 'skipped')",
            name="chk_action_items_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("action_batches.id", ondelete="CASCADE"), nullable=False)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_path: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(datetime('now'))"))
    executed_at: Mapped[Optional[str]] = mapped_column(Text)

    batch: Mapped[ActionBatch] = relationship(back_populates="items")
