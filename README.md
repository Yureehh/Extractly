# Extractly

Extractly is a Streamlit app for defining document schemas, classifying incoming files, and extracting structured metadata with traceable runs. It is designed to feel like a client-ready “Document Metadata Extraction Studio” with clear workflow steps and demo-friendly outputs.

## Quickstart

1. Create a `.env` file with your API keys:

```
OPENAI_API_KEY=your_key_here
```

2. Install dependencies (for example with `uv` or `pip`).
3. Run the app:

```
streamlit run Home.py
```

## App Navigation

- **Home**: Landing page with product highlights and quick CTAs.
- **Schema Studio**: Create, edit, validate, and export schemas with a live JSON preview.
- **Extract**: Upload single or batch documents, select routing, and run extraction.
- **Results**: Browse run history, inspect JSON/table outputs, export JSON/CSV.
- **Settings**: Review models, retries, and environment configuration.

## Schemas

- Prebuilt schemas: `schemas/prebuilt_schemas.json`
- Custom schemas: `schemas/custom_schemas.json`

Custom schemas override prebuilt ones when names overlap.

## Runs

All extraction runs are stored in `data/runs/` with input filenames, output JSON, and logs.

## Demo Script

1. Open **Schema Studio** and review a prebuilt schema (e.g., Invoice Demo).
2. Go to **Extract**, choose routing, and upload a sample document from `data/sample_docs/` or `data/imgs/`.
3. Run extraction and open **Results** to review output and export JSON/CSV.

## Notes

- Update models and retries via `.env` using the `EXTRACTLY_*` variables.
- Keep API keys in environment variables only; do not hardcode secrets.
