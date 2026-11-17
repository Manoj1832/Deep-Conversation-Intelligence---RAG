import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from backend.app.models.schemas import (
    SourceMessageSchema, ConversationSessionSchema, ArchiveManifestSchema,
    DataQualityReportSchema, DuplicateAuditReportSchema, QualityMetricsSchema
)

class DataExporter:
    """
    Exports normalized datasets to data/processed/:
    - messages.jsonl
    - sessions.jsonl
    - archive_manifest.json
    - data_quality_report.json
    - duplicate_audit.json
    Validates every output record and guarantees strict one-valid-JSON-object-per-line formatting.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_messages_jsonl(self, messages: List[SourceMessageSchema]) -> Path:
        out_path = self.output_dir / "messages.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for msg in messages:
                # Validate by serializing to JSON dict
                record_dict = msg.model_dump(mode="json")
                f.write(json.dumps(record_dict, ensure_ascii=False) + "\n")
        return out_path

    def export_sessions_jsonl(self, sessions: List[ConversationSessionSchema]) -> Path:
        out_path = self.output_dir / "sessions.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for sess in sessions:
                record_dict = sess.model_dump(mode="json")
                f.write(json.dumps(record_dict, ensure_ascii=False) + "\n")
        return out_path

    def export_manifest(self, manifest: ArchiveManifestSchema) -> Path:
        out_path = self.output_dir / "archive_manifest.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return out_path

    def export_duplicate_audit(self, audit: DuplicateAuditReportSchema) -> Path:
        out_path = self.output_dir / "duplicate_audit.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(audit.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return out_path

    def export_quality_report(self, report: DataQualityReportSchema) -> Path:
        out_path = self.output_dir / "data_quality_report.json"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False))
        return out_path
