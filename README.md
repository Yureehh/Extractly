# Extractly — Document Metadata Extraction Studio

Extractly is a Streamlit app for defining document schemas, classifying incoming files, and extracting structured metadata with traceable runs. The current version delivers a client-ready demo experience with a clean information architecture and modular codebase.

## Features
- **Schema Studio**: create, edit, validate, and export schemas with live JSON preview.
- **Extraction pipeline**: classify → extract → validate with confidence scores and OCR support.
- **Run history**: every run is stored locally with outputs, warnings, and errors.
- **Results workspace**: table view, JSON view, per-field confidence, and CSV/JSON exports.
- **Configurable LLM usage**: timeouts, retries, model selection via `.env`.

## Quickstart
```bash
# 1) Install dependencies
pip install -e .

# 2) Set API key
cp .env.example .env
# edit .env and set OPENAI_API_KEY

# 3) Run the app
streamlit run Home.py
```

## Environment Variables
```
OPENAI_API_KEY=your_key_here
CLASSIFY_MODEL=o4-mini
EXTRACT_MODEL=o4-mini
OCR_MODEL=o4-mini
EXTRACTLY_TIMEOUT_S=40
EXTRACTLY_MAX_RETRIES=2
EXTRACTLY_RETRY_BACKOFF_S=1.5
```

## Information Architecture
- **Home**: landing page + demo entry points.
- **Schema Studio**: schema creation, validation, templates, import/export.
- **Extract**: upload files and run classification + extraction.
- **Results**: browse run history and export data.
- **Settings**: environment checks and config visibility.

## Repo Structure
```
Home.py
pages/
  1_Schema_Studio.py
  2_Extract.py
  3_Results.py
  4_Settings.py
src/extractly/
  config.py
  logging.py
  domain/
  integrations/
  pipeline/
  ui/
```

## Demo Script (5 minutes)
1. Open **Home** and describe the workflow.
2. Navigate to **Schema Studio** and load the “Invoice Lite” template.
3. Save the schema, then go to **Extract**.
4. Upload `data/sample_docs/sample_invoice.txt` and run extraction.
5. Open **Results**, select the run, and export JSON/CSV.

## Samples
- Sample docs are in `data/sample_docs/`.
- Example schemas live in `schemas/`.

## Tests
```bash
pytest
```

## Notes
- Runs are stored in `./runs` (configurable).
- Configure models and timeouts via `.env`.
- The app relies on Streamlit and the OpenAI API. No secrets are committed.
