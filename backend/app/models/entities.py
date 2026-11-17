import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, BigInteger, Float, Boolean,
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class SourceArchive(Base):
    __tablename__ = "source_archives"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    archive_filename = Column(Text, nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)
    file_size_bytes = Column(BigInteger, nullable=False)
    total_lines_detected = Column(Integer, default=0)
    total_records_parsed = Column(Integer, default=0)
    earliest_message_timestamp = Column(DateTime, nullable=True)
    latest_message_timestamp = Column(DateTime, nullable=True)
    status = Column(String(30), default="processed")
    archive_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("SourceMessage", back_populates="archive", cascade="all, delete-orphan")


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    start_timestamp = Column(DateTime, nullable=False, index=True)
    end_timestamp = Column(DateTime, nullable=False, index=True)
    inactivity_threshold_hours = Column(Float, default=6.0)
    message_count = Column(Integer, default=0)
    partner_message_count = Column(Integer, default=0)
    user_message_count = Column(Integer, default=0)
    source_archive_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("SourceMessage", back_populates="session")


class SourceMessage(Base):
    __tablename__ = "source_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    archive_id = Column(String(36), ForeignKey("source_archives.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.session_id", ondelete="SET NULL"), nullable=True, index=True)
    source_message_id = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    sender = Column(String(20), nullable=False, index=True)
    original_sender = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    message_type = Column(String(30), nullable=False, index=True)
    media_type = Column(String(20), nullable=False, default="none")
    is_system_message = Column(Boolean, default=False)
    is_multiline = Column(Boolean, default=False)
    source_line_number = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    is_duplicate_across_archives = Column(Boolean, default=False)
    duplicate_archive_provenance = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    archive = relationship("SourceArchive", back_populates="messages")
    session = relationship("ConversationSession", back_populates="messages")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String(50), nullable=False)
    status = Column(String(30), default="completed")
    archives_processed = Column(JSON, default=list)
    quality_metrics = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
