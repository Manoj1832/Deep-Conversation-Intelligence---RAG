from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ZIP_DIR = BASE_DIR / "zip"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOCAL_DB_PATH = BASE_DIR / "data" / "herai_local.db"

class PipelineConfig(BaseModel):
    inactivity_threshold_hours: float = Field(default=6.0, description="Session boundary inactivity threshold in hours")
    zip_dir: Path = Field(default=ZIP_DIR)
    processed_dir: Path = Field(default=PROCESSED_DATA_DIR)
    database_url: str = Field(default=f"sqlite:///{LOCAL_DB_PATH}")
    
    # Participant mapping: maps raw WhatsApp string to normalized identity
    sender_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "Manoj": "user",
            "Sakthi": "partner",
            "sakthijayasri": "partner",
            "❤️‍🩹": "partner",
            "❤️\u200d🩹": "partner",
        }
    )

config = PipelineConfig()
