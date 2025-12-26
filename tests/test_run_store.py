from pathlib import Path

from extractly.domain.run_store import ExtractionRun, RunDocument, RunStore


def test_run_store_round_trip(tmp_path: Path):
    store = RunStore(tmp_path)
    run = ExtractionRun(
        run_id=store.create_run_id(),
        started_at="2025-01-01T00:00:00Z",
        schema_name="Invoice",
        mode="fast",
        documents=[
            RunDocument(
                filename="sample.pdf",
                document_type="Invoice",
                confidence=0.8,
                extracted={"Invoice Number": "INV-1"},
                corrected={"Invoice Number": "INV-1"},
                field_confidence={"Invoice Number": 0.8},
            )
        ],
    )

    store.save(run)
    runs = store.list_runs()
    assert runs
    loaded = store.load(run.run_id)
    assert loaded is not None
    assert loaded["schema_name"] == "Invoice"
