from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from extractly.domain.models import DocumentSchema, SchemaField
from extractly.domain.validation import validate_schema, ValidationResult


class SchemaStore:
    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir
        self.schema_dir.mkdir(parents=True, exist_ok=True)

    def list_schemas(self) -> list[DocumentSchema]:
        schemas: list[DocumentSchema] = []
        for file_path in sorted(self.schema_dir.glob("*.json")):
            with file_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            schemas.extend(self._parse_payload(payload))
        return sorted(schemas, key=lambda s: s.name.lower())

    def get_schema(self, name: str) -> DocumentSchema | None:
        for schema in self.list_schemas():
            if schema.name == name:
                return schema
        return None

    def save_schema(self, schema: DocumentSchema) -> ValidationResult:
        validation = validate_schema(schema)
        if not validation.is_valid:
            return validation

        file_slug = self._slugify(schema.name)
        file_path = self.schema_dir / f"{file_slug}.json"
        payload = {schema.name: schema.to_dict()}
        with file_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)
        return validation

    def delete_schema(self, name: str) -> bool:
        deleted = False
        for file_path in self.schema_dir.glob("*.json"):
            with file_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if name in payload:
                payload.pop(name)
                deleted = True
                if payload:
                    with file_path.open("w", encoding="utf-8") as fp:
                        json.dump(payload, fp, indent=2, ensure_ascii=False)
                else:
                    file_path.unlink(missing_ok=True)
        return deleted

    def import_payload(self, payload: dict) -> list[DocumentSchema]:
        schemas = self._parse_payload(payload)
        for schema in schemas:
            self.save_schema(schema)
        return schemas

    def export_schema(self, schema: DocumentSchema) -> str:
        return json.dumps({schema.name: schema.to_dict()}, indent=2, ensure_ascii=False)

    @staticmethod
    def _slugify(name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
        return cleaned.strip("-").lower() or "schema"

    def _parse_payload(self, payload: dict) -> list[DocumentSchema]:
        schemas: list[DocumentSchema] = []
        for name, data in payload.items():
            if isinstance(data, list):
                fields = [self._parse_field(field) for field in data]
                schemas.append(DocumentSchema(name=name, fields=fields))
                continue

            description = data.get("description", "")
            version = data.get("version", "v1")
            raw_fields = data.get("fields", [])
            fields = [self._parse_field(field) for field in raw_fields]
            schemas.append(
                DocumentSchema(
                    name=name,
                    description=description,
                    fields=fields,
                    version=version,
                )
            )
        return schemas

    @staticmethod
    def _parse_field(field: dict) -> SchemaField:
        return SchemaField(
            name=str(field.get("name", "")).strip(),
            field_type=field.get("type", field.get("field_type", "string")),
            required=bool(field.get("required", False)),
            description=str(field.get("description", "")),
            example=str(field.get("example", "")),
            enum_values=list(field.get("enum", field.get("enum_values", [])) or []),
        )


def schemas_to_table(schema: DocumentSchema) -> list[dict]:
    return [
        {
            "name": field.name,
            "type": field.field_type,
            "required": field.required,
            "description": field.description,
            "example": field.example,
            "enum": ", ".join(field.enum_values),
        }
        for field in schema.fields
    ]


def table_to_schema(name: str, description: str, rows: Iterable[dict]) -> DocumentSchema:
    fields: list[SchemaField] = []
    for row in rows:
        enum_values = [
            item.strip()
            for item in str(row.get("enum", "")).split(",")
            if item.strip()
        ]
        fields.append(
            SchemaField(
                name=str(row.get("name", "")).strip(),
                field_type=row.get("type", "string"),
                required=bool(row.get("required", False)),
                description=str(row.get("description", "")).strip(),
                example=str(row.get("example", "")).strip(),
                enum_values=enum_values,
            )
        )
    return DocumentSchema(name=name, description=description, fields=fields)
