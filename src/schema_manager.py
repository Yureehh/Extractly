import os
import json
from glob import glob
from pathlib import Path


class SchemaManager:
    """
    Load built-in and custom schemas from schemas/ directory.
    Schemas are JSON files: {"type": [{"name":...,"description":...}, ...]}
    """

    def __init__(self, schema_dir="schemas"):
        self.schema_dir = schema_dir
        self.schemas = {}
        self._load_schemas()

    def _load_schemas(self):
        for f in glob(os.path.join(self.schema_dir, "*.json")):
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for doc_type, payload in data.items():
                # 🔄 if payload is list → wrap in new structure
                if isinstance(payload, list):
                    payload = {"description": "", "fields": payload}
                self.schemas[doc_type] = payload

    def add_custom(self, custom: dict):
        wrapped = {
            k: {"description": "", "fields": v} if isinstance(v, list) else v
            for k, v in custom.items()
        }
        self.schemas.update(wrapped)

    def get_types(self):
        return sorted(self.schemas.keys())

    def get(self, doc_type: str) -> list[dict]:
        return (self.schemas.get(doc_type) or {}).get("fields", [])

    def get_description(self, doc_type: str) -> str:
        return (self.schemas.get(doc_type) or {}).get("description", "")

    def dump_custom(self, path: str | Path):
        """Persist current schemas to JSON (helper)."""
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(self.schemas, fp, indent=2, ensure_ascii=False)

    def delete(self, doc_type: str) -> bool:
        """Remove a doc-type. Return True if it existed."""
        return self.schemas.pop(doc_type, None) is not None

    def rename(self, old: str, new: str) -> None:
        """Rename a doc-type (overwriting 'new' if it exists)."""
        if old in self.schemas:
            self.schemas[new] = self.schemas.pop(old)
