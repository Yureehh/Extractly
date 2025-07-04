import os
import json
from glob import glob


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
        files = glob(os.path.join(self.schema_dir, "*.json"))
        for f in files:
            with open(f, "r") as fp:
                data = json.load(fp)
                for doc_type, fields in data.items():
                    self.schemas[doc_type] = fields

    def add_custom(self, custom: dict):
        self.schemas.update(custom)

    def get_types(self):
        return sorted(self.schemas.keys())

    def get(self, doc_type: str):
        return self.schemas.get(doc_type)
