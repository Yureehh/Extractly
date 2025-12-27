from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.domain.models import DocumentSchema, SchemaField
from src.domain.validation import validate_schema, ValidationResult


class SchemaStore:
    def __init__(self, prebuilt_path: Path, custom_path: Path):
        self.prebuilt_path = prebuilt_path
        self.custom_path = custom_path
        self.prebuilt_path.parent.mkdir(parents=True, exist_ok=True)
        self.custom_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.prebuilt_path.exists():
            self._write_payload(self.prebuilt_path, {})
        if not self.custom_path.exists():
            self._write_payload(self.custom_path, {})

    def list_schemas(self) -> list[DocumentSchema]:
        prebuilt_payload = self._load_payload(self.prebuilt_path)
        custom_payload = self._load_payload(self.custom_path)
        prebuilt_payload = self._dedupe_prebuilt(prebuilt_payload, custom_payload)
        prebuilt_map = self._parse_payload_map(prebuilt_payload)
        custom_map = self._parse_payload_map(custom_payload)
        merged = {**prebuilt_map, **custom_map}
        return sorted(merged.values(), key=lambda s: s.name.lower())

    def get_schema(self, name: str) -> DocumentSchema | None:
        custom_payload = self._load_payload(self.custom_path)
        if name in custom_payload:
            return self._parse_payload_map({name: custom_payload[name]}).get(name)
        prebuilt_payload = self._load_payload(self.prebuilt_path)
        if name in prebuilt_payload:
            return self._parse_payload_map({name: prebuilt_payload[name]}).get(name)
        return None

    def get_schema_source(self, name: str) -> str | None:
        custom_payload = self._load_payload(self.custom_path)
        if name in custom_payload:
            return "custom"
        prebuilt_payload = self._load_payload(self.prebuilt_path)
        if name in prebuilt_payload:
            return "prebuilt"
        return None

    def save_schema(
        self,
        schema: DocumentSchema,
        *,
        source: str | None = None,
        original_name: str | None = None,
    ) -> ValidationResult:
        validation = validate_schema(schema)
        if not validation.is_valid:
            return validation

        prebuilt_payload = self._load_payload(self.prebuilt_path)
        custom_payload = self._load_payload(self.custom_path)
        prebuilt_payload = self._dedupe_prebuilt(prebuilt_payload, custom_payload)

        if source == "prebuilt":
            target_payload = prebuilt_payload
            target_path = self.prebuilt_path
            if schema.name in custom_payload:
                target_payload = custom_payload
                target_path = self.custom_path
        elif source == "custom":
            target_payload = custom_payload
            target_path = self.custom_path
        else:
            target_payload = custom_payload
            target_path = self.custom_path

        if original_name and original_name != schema.name:
            target_payload.pop(original_name, None)

        target_payload[schema.name] = schema.to_dict()
        self._write_payload(target_path, target_payload)

        if target_path == self.custom_path and schema.name in prebuilt_payload:
            prebuilt_payload.pop(schema.name, None)
            self._write_payload(self.prebuilt_path, prebuilt_payload)
        return validation

    def delete_schema(self, name: str) -> bool:
        custom_payload = self._load_payload(self.custom_path)
        if name in custom_payload:
            custom_payload.pop(name)
            self._write_payload(self.custom_path, custom_payload)
            return True

        prebuilt_payload = self._load_payload(self.prebuilt_path)
        if name in prebuilt_payload:
            prebuilt_payload.pop(name)
            self._write_payload(self.prebuilt_path, prebuilt_payload)
            return True
        return False

    def import_payload(self, payload: dict) -> list[DocumentSchema]:
        schemas = list(self._parse_payload_map(payload).values())
        custom_payload = self._load_payload(self.custom_path)
        prebuilt_payload = self._load_payload(self.prebuilt_path)
        prebuilt_payload = self._dedupe_prebuilt(prebuilt_payload, custom_payload)

        for schema in schemas:
            validation = validate_schema(schema)
            if not validation.is_valid:
                continue
            custom_payload[schema.name] = schema.to_dict()
            prebuilt_payload.pop(schema.name, None)

        self._write_payload(self.custom_path, custom_payload)
        self._write_payload(self.prebuilt_path, prebuilt_payload)
        return schemas

    def import_prebuilt_payload(self, payload: dict) -> list[DocumentSchema]:
        schemas = list(self._parse_payload_map(payload).values())
        prebuilt_payload = self._load_payload(self.prebuilt_path)
        custom_payload = self._load_payload(self.custom_path)

        for schema in schemas:
            validation = validate_schema(schema)
            if not validation.is_valid:
                continue
            prebuilt_payload[schema.name] = schema.to_dict()

        prebuilt_payload = self._dedupe_prebuilt(prebuilt_payload, custom_payload)
        self._write_payload(self.prebuilt_path, prebuilt_payload)
        return schemas

    def export_schema(self, schema: DocumentSchema) -> str:
        return json.dumps({schema.name: schema.to_dict()}, indent=2, ensure_ascii=False)

    @staticmethod
    def _load_payload(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict) -> None:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)

    def _dedupe_prebuilt(self, prebuilt: dict, custom: dict) -> dict:
        duplicate_names = set(prebuilt).intersection(custom)
        if not duplicate_names:
            return prebuilt
        cleaned = dict(prebuilt)
        for name in duplicate_names:
            cleaned.pop(name, None)
        self._write_payload(self.prebuilt_path, cleaned)
        return cleaned

    def _parse_payload_map(self, payload: dict) -> dict[str, DocumentSchema]:
        schemas: dict[str, DocumentSchema] = {}
        for name, data in payload.items():
            if isinstance(data, list):
                fields = [self._parse_field(field) for field in data]
                schemas[name] = DocumentSchema(name=name, fields=fields)
                continue

            description = data.get("description", "")
            version = data.get("version", "v1")
            raw_fields = data.get("fields", [])
            fields = [self._parse_field(field) for field in raw_fields]
            schemas[name] = DocumentSchema(
                name=name,
                description=description,
                fields=fields,
                version=version,
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


def table_to_schema(
    name: str, description: str, rows: Iterable[dict]
) -> DocumentSchema:
    fields: list[SchemaField] = []
    for row in rows:
        enum_values = [
            item.strip() for item in str(row.get("enum", "")).split(",") if item.strip()
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
