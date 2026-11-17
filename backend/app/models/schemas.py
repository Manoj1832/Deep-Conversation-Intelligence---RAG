from datetime import datetime, timezone
from typing import List, Literal, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict

def utc_now():
    return datetime.now(timezone.utc)

SenderRole = Literal["partner", "user", "system"]
MessageType = Literal["text", "media", "deleted", "call_log", "system", "empty_placeholder"]
MediaType = Literal["image", "video", "audio", "sticker", "document", "gif", "contact", "none"]

class SourceMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Internal unique message identifier")
    archive_id: UUID = Field(..., description="ID of source archive")
    source_message_id: str = Field(..., description="Source-level reference e.g. archive_filename:line_number")
    timestamp: datetime = Field(..., description="Normalized UTC message timestamp")
    sender: SenderRole = Field(..., description="Normalized participant identity")
    original_sender: str = Field(..., description="Raw sender string extracted from WhatsApp export")
    body: str = Field(..., description="Verbatim message body text")
    message_type: MessageType = Field(default="text", description="Classified message type")
    media_type: MediaType = Field(default="none", description="Classified media attachment type")
    is_system_message: bool = Field(default=False, description="True for system events, call logs, encryption alerts")
    is_multiline: bool = Field(default=False, description="True if message contains newlines from multiline export")
    source_line_number: int = Field(..., description="Starting line number in raw chat text file")
    content_hash: str = Field(..., description="Deterministic SHA-256 hash for deduplication")
    is_duplicate_across_archives: bool = Field(default=False, description="True if this message appeared in multiple archives")
    duplicate_archive_provenance: List[str] = Field(default_factory=list, description="List of archive filenames containing this message")
    session_id: Optional[UUID] = Field(default=None, description="Assigned conversation session ID")
    created_at: datetime = Field(default_factory=utc_now, description="Record creation timestamp")


class ConversationSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID = Field(default_factory=uuid4, description="Unique conversation session UUID")
    start_timestamp: datetime = Field(..., description="Timestamp of first message in session")
    end_timestamp: datetime = Field(..., description="Timestamp of last message in session")
    inactivity_threshold_hours: float = Field(default=6.0, description="Inactivity threshold used for segmentation")
    message_count: int = Field(default=0, description="Total unique messages in this session")
    partner_message_count: int = Field(default=0, description="Total partner messages in session")
    user_message_count: int = Field(default=0, description="Total user messages in session")
    source_archive_ids: List[UUID] = Field(default_factory=list, description="IDs of source archives contributing to session")
    created_at: datetime = Field(default_factory=utc_now, description="Record creation timestamp")


class ArchiveManifestItem(BaseModel):
    archive_id: UUID
    original_filename: str
    file_hash_sha256: str
    file_size_bytes: int
    total_raw_lines: int
    parsed_record_count: int
    text_message_count: int
    media_message_count: int
    system_event_count: int
    deleted_message_count: int
    earliest_timestamp: Optional[str] = None
    latest_timestamp: Optional[str] = None
    status: str = "processed"


class ArchiveManifestSchema(BaseModel):
    pipeline_version: str = "2.0.0"
    generated_at: str
    total_archives: int
    archives: List[ArchiveManifestItem]


class QualityMetricsSchema(BaseModel):
    total_records_discovered: int
    successfully_parsed_records: int
    text_messages: int
    media_messages: int
    system_events: int
    deleted_messages: int
    call_logs: int
    unknown_sender_records: int
    malformed_records: int
    duplicate_records_pruned: int
    empty_placeholder_records: int
    timestamp_parsing_failures: int
    unicode_decoding_failures: int
    missing_message_bodies: int
    chronological_ordering_violations: int
    unique_messages_stored: int
    total_sessions_created: int


class DataQualityReportSchema(BaseModel):
    report_title: str = "HerAI WhatsApp Ingestion Data Quality Report"
    generated_at: str
    metrics: QualityMetricsSchema
    participant_breakdown: Dict[str, Dict[str, Any]]
    archive_reconciliation: Dict[str, Dict[str, Any]]
    reconciliation_summary: str


class DuplicateAuditItem(BaseModel):
    content_hash: str
    canonical_message_id: str
    timestamp: str
    sender: str
    body_snippet: str
    occurrences_count: int
    source_archives: List[str]


class DuplicateAuditReportSchema(BaseModel):
    generated_at: str
    total_duplicates_found: int
    unique_canonical_messages_affected: int
    duplicate_items: List[DuplicateAuditItem]
