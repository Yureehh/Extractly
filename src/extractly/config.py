from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    openai_api_key: str | None
    classify_model: str
    extract_model: str
    ocr_model: str
    request_timeout_s: int
    max_retries: int
    retry_backoff_s: float
    run_store_dir: Path
    schema_dir: Path
    sample_data_dir: Path


def load_config() -> AppConfig:
    load_dotenv(override=True)

    return AppConfig(
        app_name=os.getenv("EXTRACTLY_APP_NAME", "Extractly"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        classify_model=os.getenv("CLASSIFY_MODEL", "o4-mini"),
        extract_model=os.getenv("EXTRACT_MODEL", "o4-mini"),
        ocr_model=os.getenv("OCR_MODEL", "o4-mini"),
        request_timeout_s=int(os.getenv("EXTRACTLY_TIMEOUT_S", "40")),
        max_retries=int(os.getenv("EXTRACTLY_MAX_RETRIES", "2")),
        retry_backoff_s=float(os.getenv("EXTRACTLY_RETRY_BACKOFF_S", "1.5")),
        run_store_dir=Path(os.getenv("EXTRACTLY_RUNS_DIR", PROJECT_ROOT / "runs")),
        schema_dir=Path(os.getenv("EXTRACTLY_SCHEMAS_DIR", PROJECT_ROOT / "schemas")),
        sample_data_dir=Path(os.getenv("EXTRACTLY_SAMPLE_DATA_DIR", PROJECT_ROOT / "data" / "sample_docs")),
    )
