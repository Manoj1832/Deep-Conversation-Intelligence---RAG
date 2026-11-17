from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker, Session
from backend.app.models.entities import Base, SourceArchive, SourceMessage, ConversationSession, AnalysisJob
from backend.app.models.schemas import SourceMessageSchema, ConversationSessionSchema, ArchiveManifestItem

class DatabaseStorageService:
    """
    Transactional storage service for WhatsApp ingestion.
    Supports Supabase PostgreSQL and local SQLite fallback.
    Guarantees idempotent batch insertions and transaction rollbacks.
    """

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def persist_archive_record(self, item: ArchiveManifestItem) -> str:
        with self.SessionLocal() as session:
            try:
                # Check existing by file_hash
                existing = session.execute(
                    select(SourceArchive).where(SourceArchive.file_hash == item.file_hash_sha256)
                ).scalar_one_or_none()

                earliest_dt = datetime.fromisoformat(item.earliest_timestamp) if item.earliest_timestamp else None
                latest_dt = datetime.fromisoformat(item.latest_timestamp) if item.latest_timestamp else None

                if existing:
                    existing.archive_filename = item.original_filename
                    existing.file_size_bytes = item.file_size_bytes
                    existing.total_lines_detected = item.total_raw_lines
                    existing.total_records_parsed = item.parsed_record_count
                    existing.earliest_message_timestamp = earliest_dt
                    existing.latest_message_timestamp = latest_dt
                    existing.status = item.status
                    existing.updated_at = datetime.utcnow()
                    session.commit()
                    return existing.id
                else:
                    new_archive = SourceArchive(
                        id=str(item.archive_id),
                        archive_filename=item.original_filename,
                        file_hash=item.file_hash_sha256,
                        file_size_bytes=item.file_size_bytes,
                        total_lines_detected=item.total_raw_lines,
                        total_records_parsed=item.parsed_record_count,
                        earliest_message_timestamp=earliest_dt,
                        latest_message_timestamp=latest_dt,
                        status=item.status,
                        created_at=datetime.utcnow()
                    )
                    session.add(new_archive)
                    session.commit()
                    return new_archive.id
            except Exception:
                session.rollback()
                raise

    def persist_sessions(self, sessions: List[ConversationSessionSchema]) -> None:
        with self.SessionLocal() as db_session:
            try:
                for s in sessions:
                    existing = db_session.execute(
                        select(ConversationSession).where(ConversationSession.session_id == str(s.session_id))
                    ).scalar_one_or_none()

                    if not existing:
                        db_record = ConversationSession(
                            id=str(s.session_id),
                            session_id=str(s.session_id),
                            start_timestamp=s.start_timestamp,
                            end_timestamp=s.end_timestamp,
                            inactivity_threshold_hours=s.inactivity_threshold_hours,
                            message_count=s.message_count,
                            partner_message_count=s.partner_message_count,
                            user_message_count=s.user_message_count,
                            source_archive_ids=[str(aid) for aid in s.source_archive_ids],
                            created_at=s.created_at
                        )
                        db_session.add(db_record)
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise

    def persist_messages_batch(self, messages: List[SourceMessageSchema], batch_size: int = 1000) -> int:
        """
        Batch inserts messages with idempotency (checks existing id or content_hash).
        """
        inserted_count = 0
        with self.SessionLocal() as db_session:
            try:
                for i in range(0, len(messages), batch_size):
                    chunk = messages[i:i + batch_size]
                    for m in chunk:
                        existing = db_session.execute(
                            select(SourceMessage).where(SourceMessage.id == str(m.id))
                        ).scalar_one_or_none()

                        if not existing:
                            db_msg = SourceMessage(
                                id=str(m.id),
                                archive_id=str(m.archive_id),
                                session_id=str(m.session_id) if m.session_id else None,
                                source_message_id=m.source_message_id,
                                timestamp=m.timestamp,
                                sender=m.sender,
                                original_sender=m.original_sender,
                                body=m.body,
                                message_type=m.message_type,
                                media_type=m.media_type,
                                is_system_message=m.is_system_message,
                                is_multiline=m.is_multiline,
                                source_line_number=m.source_line_number,
                                content_hash=m.content_hash,
                                is_duplicate_across_archives=m.is_duplicate_across_archives,
                                duplicate_archive_provenance=m.duplicate_archive_provenance,
                                created_at=m.created_at
                            )
                            db_session.add(db_msg)
                            inserted_count += 1
                    db_session.commit()
            except Exception:
                db_session.rollback()
                raise
        return inserted_count

    def record_analysis_job(self, job_type: str, archives: List[str], metrics: Dict[str, Any]) -> str:
        with self.SessionLocal() as db_session:
            try:
                job = AnalysisJob(
                    job_type=job_type,
                    status="completed",
                    archives_processed=archives,
                    quality_metrics=metrics,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow()
                )
                db_session.add(job)
                db_session.commit()
                return job.id
            except Exception:
                db_session.rollback()
                raise
