# Extractly

## Overview
A plug-and-play Python framework to classify and extract metadata from PDFs and images using a hybrid OCR + GPT pipeline. Supports built-in and custom document types with editable schemas.

## Features
- **Modular pipeline**: Preprocessing, classification, extraction, validation, export.
- **Hybrid OCR + LLM**: LLM (configurable) for robust extraction.
- **Custom schemas**: Define new document types and field descriptors via JSON in `schemas/` or input in UI.
- **Configurable models**: Choose between `gpt-o4-mini`, `gpt-o3`, `gpt-4o`, etc.
- **Validation & context**: Extracted values accompanied by context snippets and LLM reasoning.
- **CLI & UI**: Streamlit app and CLI interface for automation and demos.
- **Caching & metrics**: Preprocess results cached to speed up repeated runs; timings logged per step.
- **Export options**: JSON, CSV, Excel downloads.

## Getting Started
1. **Clone repo**
   ```bash
   git clone https://github.com/yourorg/universal_extractor.git
   cd universal_extractor
   ```
2. **Create `.env` with your OpenAI key**
   ```bash
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   ```
3. **Run locally**
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. **Or with Docker**
   ```bash
   docker build -t universal_extractor .
   docker run -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8501:8501 universal_extractor
   ```

## Directory Structure
- `app.py`: Streamlit frontend
- `cli.py`: Command-line interface
- `schemas/`: JSON schema files for built-in and custom types
- `utils/`: Core modules (preprocess, schema management, OpenAI client, classification, extraction)


## Extending
- Add new schema JSON to `schemas/`, restart app, it appears automatically.
- Implement additional OCR engines by extending `utils/preprocess.py`.
- Swap or fine-tune models via `utils/openai_client.py`.


# Future Work

## Code Improvements
- Metaprompting sui tipi di documenti attesi
- Aggiustare cards in Home (feedbacks are scuffed overall)
- Rivedere la confidence (mettere nel json dei controlli extra tipo rgex o agenti )
- TO DISCUSS: Improve from errors, saving last N feedbacks for a give doc type (only incorrect ones?) and pass in context

## Business Improvements
- Tracciare kpi
- Fare sides fighe in cui dici flusso ed “agenti”
