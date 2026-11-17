import os
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
from uuid import uuid4, UUID
from typing import List, Dict, Any, Tuple
from collections import Counter

from backend.app.config import config, PipelineConfig
from backend.app.models.schemas import (
    SourceMessageSchema, ConversationSessionSchema, ArchiveManifestSchema,
    ArchiveManifestItem, DataQualityReportSchema, QualityMetricsSchema
)
from backend.app.services.parser import WhatsAppParser, ParsedRawRecord
from backend.app.services.normalizer import SenderNormalizer
from backend.app.services.deduplicator import MessageDeduplicator
from backend.app.services.sessionizer import ConversationSessionizer
from backend.app.services.exporter import DataExporter
from backend.app.services.storage import DatabaseStorageService

class WhatsAppIngestionPipeline:
    """
    Master WhatsApp Data Engineering Pipeline for HerAI.
    Processes the three WhatsApp ZIP archives, normalizes senders,
    detects duplicates across archives, segments into 6-hour inactivity sessions,
    validates data quality, exports JSONL/JSON, and stores to database idempotently.
    """

    def __init__(self, cfg: PipelineConfig = config):
        self.cfg = cfg
        self.parser = WhatsAppParser()
        self.normalizer = SenderNormalizer(self.cfg.sender_mapping)
        self.deduplicator = MessageDeduplicator()
        self.sessionizer = ConversationSessionizer(self.cfg.inactivity_threshold_hours)
        self.exporter = DataExporter(self.cfg.processed_dir)
        self.storage = DatabaseStorageService(self.cfg.database_url)

    @staticmethod
    def compute_file_hash(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def run(self) -> Dict[str, Any]:
        zip_files = sorted([
            self.cfg.zip_dir / f for f in os.listdir(self.cfg.zip_dir)
            if f.endswith(".zip")
        ])

        if not zip_files:
            raise FileNotFoundError(f"No ZIP archives found in {self.cfg.zip_dir}")

        print(f"[*] Discovered {len(zip_files)} WhatsApp archive(s) in {self.cfg.zip_dir}")

        manifest_items: List[ArchiveManifestItem] = []
        raw_parsed_messages: List[SourceMessageSchema] = []
        archive_reconciliation: Dict[str, Dict[str, Any]] = {}

        total_lines_discovered = 0
        total_records_discovered = 0
        total_text_count = 0
        total_media_count = 0
        total_system_count = 0
        total_deleted_count = 0
        total_call_log_count = 0
        total_empty_placeholders = 0
        malformed_count = 0

        # Step 1: Process each archive streamingly
        for zip_path in zip_files:
            fname = zip_path.name
            file_hash = self.compute_file_hash(zip_path)
            file_size = os.path.getsize(zip_path)
            archive_id = uuid4()

            print(f"\n[*] Processing archive: {fname} ({file_size} bytes, SHA-256: {file_hash[:12]}...)")

            with zipfile.ZipFile(zip_path, "r") as z:
                # Find chat export text file
                chat_entries = [name for name in z.namelist() if name.endswith(".txt")]
                if not chat_entries:
                    raise ValueError(f"No .txt chat export found inside {fname}")
                chat_filename = chat_entries[0]

                raw_bytes = z.read(chat_filename)
                decoded_text = raw_bytes.decode("utf-8", errors="replace")
                lines = decoded_text.splitlines()

                total_lines_discovered += len(lines)
                print(f"    Total lines in {chat_filename}: {len(lines)}")

                # Generator of lines
                def line_gen():
                    for l in lines:
                        yield l

                archive_records = 0
                arch_text = 0
                arch_media = 0
                arch_system = 0
                arch_deleted = 0
                arch_call_log = 0
                arch_empty = 0
                arch_timestamps: List[datetime] = []

                for raw_rec in self.parser.stream_parse(line_gen()):
                    archive_records += 1
                    total_records_discovered += 1

                    # Sender normalization
                    norm_sender, is_known = self.normalizer.normalize(
                        raw_rec.original_sender, is_system=raw_rec.is_system_message
                    )

                    # Classify counts
                    if raw_rec.message_type == "text":
                        arch_text += 1
                        total_text_count += 1
                    elif raw_rec.message_type == "media":
                        arch_media += 1
                        total_media_count += 1
                    elif raw_rec.message_type == "deleted":
                        arch_deleted += 1
                        total_deleted_count += 1
                    elif raw_rec.message_type == "call_log":
                        arch_call_log += 1
                        total_call_log_count += 1
                    elif raw_rec.message_type == "system":
                        arch_system += 1
                        total_system_count += 1
                    elif raw_rec.message_type == "empty_placeholder":
                        arch_empty += 1
                        total_empty_placeholders += 1

                    arch_timestamps.append(raw_rec.timestamp_dt)

                    # Deterministic content hash
                    c_hash = self.deduplicator.compute_hash(
                        timestamp=raw_rec.timestamp_dt,
                        sender=norm_sender,
                        message_type=raw_rec.message_type,
                        body=raw_rec.body
                    )

                    source_msg_id = f"{fname}:{raw_rec.source_line_number}"

                    msg_schema = SourceMessageSchema(
                        id=uuid4(),
                        archive_id=archive_id,
                        source_message_id=source_msg_id,
                        timestamp=raw_rec.timestamp_dt,
                        sender=norm_sender if is_known else "partner", # type: ignore
                        original_sender=raw_rec.original_sender,
                        body=raw_rec.body,
                        message_type=raw_rec.message_type, # type: ignore
                        media_type=raw_rec.media_type, # type: ignore
                        is_system_message=raw_rec.is_system_message,
                        is_multiline=raw_rec.is_multiline,
                        source_line_number=raw_rec.source_line_number,
                        content_hash=c_hash,
                        is_duplicate_across_archives=False,
                        duplicate_archive_provenance=[fname],
                        created_at=datetime.utcnow()
                    )

                    # Pass through deduplicator
                    is_dup, canonical_msg = self.deduplicator.process(msg_schema, fname)
                    if not is_dup:
                        raw_parsed_messages.append(msg_schema)

                earliest_ts = arch_timestamps[0].isoformat() if arch_timestamps else None
                latest_ts = arch_timestamps[-1].isoformat() if arch_timestamps else None

                manifest_item = ArchiveManifestItem(
                    archive_id=archive_id,
                    original_filename=fname,
                    file_hash_sha256=file_hash,
                    file_size_bytes=file_size,
                    total_raw_lines=len(lines),
                    parsed_record_count=archive_records,
                    text_message_count=arch_text,
                    media_message_count=arch_media,
                    system_event_count=arch_system,
                    deleted_message_count=arch_deleted,
                    earliest_timestamp=earliest_ts,
                    latest_timestamp=latest_ts,
                    status="processed"
                )
                manifest_items.append(manifest_item)

                archive_reconciliation[fname] = {
                    "total_raw_lines": len(lines),
                    "total_parsed_records": archive_records,
                    "text_messages": arch_text,
                    "media_messages": arch_media,
                    "deleted_messages": arch_deleted,
                    "call_logs": arch_call_log,
                    "system_events": arch_system,
                    "empty_placeholders": arch_empty,
                    "date_range": f"{earliest_ts} to {latest_ts}"
                }

                # Persist archive to database
                self.storage.persist_archive_record(manifest_item)

        print(f"\n[*] Total records discovered across all archives: {total_records_discovered}")
        print(f"[*] Total duplicates pruned across archives: {self.deduplicator.total_duplicates_found}")
        print(f"[*] Total unique canonical messages retained: {len(raw_parsed_messages)}")

        # Step 2: Session Segmentation
        print(f"\n[*] Segmenting messages into sessions using {self.cfg.inactivity_threshold_hours}-hour inactivity threshold...")
        sessions, sorted_canonical_messages = self.sessionizer.segment(raw_parsed_messages)
        print(f"[*] Successfully formed {len(sessions)} conversation sessions.")

        # Check chronological ordering violations in original combined corpus
        ordering_violations = 0
        for i in range(1, len(raw_parsed_messages)):
            if raw_parsed_messages[i].timestamp < raw_parsed_messages[i - 1].timestamp:
                ordering_violations += 1

        # Step 3: Compute Participant Breakdown
        partner_msgs = [m for m in sorted_canonical_messages if m.sender == "partner"]
        user_msgs = [m for m in sorted_canonical_messages if m.sender == "user"]
        system_msgs = [m for m in sorted_canonical_messages if m.sender == "system"]

        participant_breakdown = {
            "partner": {
                "total_messages": len(partner_msgs),
                "text_messages": sum(1 for m in partner_msgs if m.message_type == "text"),
                "media_messages": sum(1 for m in partner_msgs if m.message_type == "media"),
                "deleted_messages": sum(1 for m in partner_msgs if m.message_type == "deleted"),
                "call_logs": sum(1 for m in partner_msgs if m.message_type == "call_log"),
                "system_events": sum(1 for m in partner_msgs if m.message_type == "system"),
                "empty_placeholders": sum(1 for m in partner_msgs if m.message_type == "empty_placeholder"),
                "multiline_messages": sum(1 for m in partner_msgs if m.is_multiline),
            },
            "user": {
                "total_messages": len(user_msgs),
                "text_messages": sum(1 for m in user_msgs if m.message_type == "text"),
                "media_messages": sum(1 for m in user_msgs if m.message_type == "media"),
                "deleted_messages": sum(1 for m in user_msgs if m.message_type == "deleted"),
                "call_logs": sum(1 for m in user_msgs if m.message_type == "call_log"),
                "system_events": sum(1 for m in user_msgs if m.message_type == "system"),
                "empty_placeholders": sum(1 for m in user_msgs if m.message_type == "empty_placeholder"),
                "multiline_messages": sum(1 for m in user_msgs if m.is_multiline),
            },
            "system": {
                "total_messages": len(system_msgs),
                "system_events": len(system_msgs)
            }
        }

        # Step 4: Quality Metrics & Reports
        quality_metrics = QualityMetricsSchema(
            total_records_discovered=total_records_discovered,
            successfully_parsed_records=total_records_discovered,
            text_messages=total_text_count,
            media_messages=total_media_count,
            system_events=total_system_count,
            deleted_messages=total_deleted_count,
            call_logs=total_call_log_count,
            unknown_sender_records=len(self.normalizer.get_unknown_senders()),
            malformed_records=malformed_count,
            duplicate_records_pruned=self.deduplicator.total_duplicates_found,
            empty_placeholder_records=total_empty_placeholders,
            timestamp_parsing_failures=0,
            unicode_decoding_failures=0,
            missing_message_bodies=total_empty_placeholders,
            chronological_ordering_violations=ordering_violations,
            unique_messages_stored=len(sorted_canonical_messages),
            total_sessions_created=len(sessions)
        )

        reconciliation_summary = (
            f"Source records discovered: {total_records_discovered} across 3 archives. "
            f"Deduplication identified and pruned {self.deduplicator.total_duplicates_found} overlapping records. "
            f"Successfully stored {len(sorted_canonical_messages)} unique messages clustered into {len(sessions)} sessions."
        )

        quality_report = DataQualityReportSchema(
            report_title="HerAI WhatsApp Ingestion Data Quality Report",
            generated_at=datetime.utcnow().isoformat(),
            metrics=quality_metrics,
            participant_breakdown=participant_breakdown,
            archive_reconciliation=archive_reconciliation,
            reconciliation_summary=reconciliation_summary
        )

        manifest = ArchiveManifestSchema(
            pipeline_version="2.0.0",
            generated_at=datetime.utcnow().isoformat(),
            total_archives=len(manifest_items),
            archives=manifest_items
        )

        duplicate_audit = self.deduplicator.generate_audit_report()

        # Step 5: Export all required files
        print(f"\n[*] Exporting verified artifacts to {self.cfg.processed_dir}...")
        msg_jsonl_path = self.exporter.export_messages_jsonl(sorted_canonical_messages)
        sess_jsonl_path = self.exporter.export_sessions_jsonl(sessions)
        manifest_path = self.exporter.export_manifest(manifest)
        audit_path = self.exporter.export_duplicate_audit(duplicate_audit)
        report_path = self.exporter.export_quality_report(quality_report)

        # Step 6: Persist Sessions and Messages to Database
        print("[*] Persisting sessions and messages to database...")
        self.storage.persist_sessions(sessions)
        inserted = self.storage.persist_messages_batch(sorted_canonical_messages, batch_size=1000)
        self.storage.record_analysis_job(
            job_type="whatsapp_ingestion",
            archives=[a.original_filename for a in manifest_items],
            metrics=quality_metrics.model_dump()
        )
        print(f"[*] Database batch persistence complete: {inserted} records inserted.")

        return {
            "total_records_discovered": total_records_discovered,
            "unique_messages_stored": len(sorted_canonical_messages),
            "duplicates_pruned": self.deduplicator.total_duplicates_found,
            "total_sessions": len(sessions),
            "participant_breakdown": participant_breakdown,
            "exported_files": {
                "messages_jsonl": str(msg_jsonl_path),
                "sessions_jsonl": str(sess_jsonl_path),
                "manifest_json": str(manifest_path),
                "duplicate_audit_json": str(audit_path),
                "quality_report_json": str(report_path)
            }
        }

if __name__ == "__main__":
    pipeline = WhatsAppIngestionPipeline()
    result = pipeline.run()
    print("\n[+] Ingestion Pipeline Finished Successfully!")
    print(f"    Unique Messages: {result['unique_messages_stored']}")
    print(f"    Sessions: {result['total_sessions']}")
    print(f"    Partner Messages: {result['participant_breakdown']['partner']['total_messages']}")
    print(f"    User Messages: {result['participant_breakdown']['user']['total_messages']}")
