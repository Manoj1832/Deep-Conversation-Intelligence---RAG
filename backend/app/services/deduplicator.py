import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from backend.app.models.schemas import SourceMessageSchema, DuplicateAuditItem, DuplicateAuditReportSchema

@dataclass
class CanonicalRecord:
    canonical_message: SourceMessageSchema
    source_archives: List[str] = field(default_factory=list)
    occurrence_count: int = 1

class MessageDeduplicator:
    """
    Deterministic duplicate detection engine.
    Computes SHA-256 hash across (normalized_timestamp, sender, message_type, verbatim_body).
    Legitimate repeated messages ('seri', 'okay', emojis) at different timestamps are PRESERVED.
    Identical messages occurring across overlapping archive exports are deduplicated,
    with provenance preserved across all source archives.
    """

    def __init__(self):
        # content_hash -> CanonicalRecord
        self.seen_records: Dict[str, CanonicalRecord] = {}
        self.duplicate_audit_items: List[DuplicateAuditItem] = []
        self.total_duplicates_found: int = 0

    @staticmethod
    def compute_hash(timestamp: datetime, sender: str, message_type: str, body: str) -> str:
        """
        Generates deterministic SHA-256 hash.
        """
        ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        raw_key = f"{ts_str}|{sender}|{message_type}|{body}"
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def process(self, message: SourceMessageSchema, archive_name: str) -> Tuple[bool, SourceMessageSchema]:
        """
        Processes a message:
        Returns (is_duplicate, canonical_or_updated_message)
        If duplicate: returns (True, updated_canonical_message with added provenance)
        If unique: returns (False, newly_registered_message)
        """
        content_hash = message.content_hash

        if content_hash in self.seen_records:
            # Duplicate found across archives or within archive
            canonical = self.seen_records[content_hash]
            canonical.occurrence_count += 1
            if archive_name not in canonical.source_archives:
                canonical.source_archives.append(archive_name)
            
            # Flag canonical record
            canonical.canonical_message.is_duplicate_across_archives = True
            canonical.canonical_message.duplicate_archive_provenance = list(canonical.source_archives)
            
            self.total_duplicates_found += 1
            return True, canonical.canonical_message
        else:
            # First time seeing this message
            message.duplicate_archive_provenance = [archive_name]
            canonical = CanonicalRecord(
                canonical_message=message,
                source_archives=[archive_name],
                occurrence_count=1
            )
            self.seen_records[content_hash] = canonical
            return False, message

    def generate_audit_report(self) -> DuplicateAuditReportSchema:
        """
        Compiles the duplicate audit report detailing every deduplicated record.
        """
        audit_items: List[DuplicateAuditItem] = []
        for content_hash, rec in self.seen_records.items():
            if rec.occurrence_count > 1:
                msg = rec.canonical_message
                snippet = msg.body[:80].replace('\n', ' ') if msg.body else '[empty body]'
                audit_items.append(
                    DuplicateAuditItem(
                        content_hash=content_hash,
                        canonical_message_id=str(msg.id),
                        timestamp=msg.timestamp.isoformat(),
                        sender=msg.sender,
                        body_snippet=snippet,
                        occurrences_count=rec.occurrence_count,
                        source_archives=rec.source_archives
                    )
                )

        return DuplicateAuditReportSchema(
            generated_at=datetime.utcnow().isoformat(),
            total_duplicates_found=self.total_duplicates_found,
            unique_canonical_messages_affected=len(audit_items),
            duplicate_items=audit_items
        )

    def get_canonical_messages(self) -> List[SourceMessageSchema]:
        """
        Returns all unique canonical messages.
        """
        return [rec.canonical_message for rec in self.seen_records.values()]
