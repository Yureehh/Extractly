from __future__ import annotations

from dataclasses import dataclass, field

from extractly.domain.models import DocumentSchema, FIELD_TYPES


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_schema(schema: DocumentSchema) -> ValidationResult:
    result = ValidationResult()

    if not schema.name.strip():
        result.errors.append("Schema name is required.")

    seen_names = set()
    for idx, field in enumerate(schema.fields, start=1):
        if not field.name.strip():
            result.errors.append(f"Field #{idx} is missing a name.")
            continue

        if field.name in seen_names:
            result.errors.append(f"Field name '{field.name}' is duplicated.")
        seen_names.add(field.name)

        if field.field_type not in FIELD_TYPES:
            result.errors.append(
                f"Field '{field.name}' has invalid type '{field.field_type}'."
            )

        if field.field_type == "enum" and not field.enum_values:
            result.errors.append(
                f"Field '{field.name}' is enum but has no enum values."
            )

        if field.enum_values:
            if len(set(field.enum_values)) != len(field.enum_values):
                result.errors.append(
                    f"Field '{field.name}' has duplicate enum values."
                )

    if not schema.fields:
        result.errors.append("At least one field is required.")

    if schema.description and len(schema.description) < 10:
        result.warnings.append("Schema description is very short.")

    return result
