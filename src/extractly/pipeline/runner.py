from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from PIL import Image

from extractly.domain.models import DocumentSchema
from extractly.domain.run_store import ExtractionRun, RunDocument, RunStore
from extractly.integrations.ocr import run_ocr
from extractly.pipeline.classification import classify_document
from extractly.pipeline.extraction import extract_metadata
from extractly.logging import get_logger


logger = get_logger(__name__)


@dataclass
class PipelineOptions:
    enable_ocr: bool = False
    compute_confidence: bool = False
    mode: str = "fast"
    classifier_prompt: str | None = None
    extraction_prompt: str | None = None


def run_pipeline(
    *,
    files: list[dict[str, Any]],
    schema: DocumentSchema,
    candidates: list[str],
    run_store: RunStore,
    options: PipelineOptions,
) -> ExtractionRun:
    run_id = run_store.create_run_id()
    logs: list[str] = []
    documents: list[RunDocument] = []

    for payload in files:
        filename = payload["name"]
        images: list[Image.Image] = payload["images"]

        logs.append(f"Parsing {filename}")
        ocr_text = payload.get("ocr_text")
        if ocr_text is None and options.enable_ocr:
            ocr_text = run_ocr(images)

        doc_type_override = payload.get("doc_type_override")
        if doc_type_override:
            doc_type = doc_type_override
            confidence = None
            logs.append(f"Using provided document type for {filename}: {doc_type}")
        else:
            classification = classify_document(
                images,
                candidates,
                use_confidence=options.compute_confidence,
                system_prompt=options.classifier_prompt,
            )
            doc_type = classification.get("doc_type", "Unknown")
            confidence = classification.get("confidence")
            logs.append(f"Classified {filename} as {doc_type}")

        warnings: list[str] = []
        errors: list[str] = []
        extracted: dict[str, Any] = {}
        field_confidence: dict[str, float] = {}

        if doc_type in {"Unknown", "Other"}:
            warnings.append("Document type is unknown. Extraction skipped.")
        else:
            try:
                extraction = extract_metadata(
                    images,
                    schema.fields,
                    ocr_text=ocr_text,
                    with_confidence=options.compute_confidence,
                    system_prompt=options.extraction_prompt,
                )
                extracted = extraction.get("metadata", {})
                field_confidence = extraction.get("confidence", {})
            except Exception as exc:
                logger.error("Extraction failed for %s: %s", filename, exc)
                errors.append(str(exc))

        documents.append(
            RunDocument(
                filename=filename,
                document_type=doc_type,
                confidence=confidence,
                extracted=extracted,
                corrected=extracted.copy(),
                field_confidence=field_confidence,
                warnings=warnings,
                errors=errors,
            )
        )

    run = ExtractionRun(
        run_id=run_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        schema_name=schema.name,
        mode=options.mode,
        documents=documents,
        logs=logs,
    )
    run_store.save(run)
    return run
