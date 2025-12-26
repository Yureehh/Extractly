from extractly.domain.models import DocumentSchema, SchemaField
from extractly.domain.validation import validate_schema


def test_validate_schema_detects_errors():
    schema = DocumentSchema(
        name="",
        fields=[
            SchemaField(name="", field_type="string"),
            SchemaField(name="status", field_type="enum", enum_values=[]),
            SchemaField(name="status", field_type="string"),
        ],
    )

    result = validate_schema(schema)
    assert not result.is_valid
    assert "Schema name is required." in result.errors
    assert any("Field #1" in err for err in result.errors)
    assert any("enum" in err for err in result.errors)
    assert any("duplicated" in err for err in result.errors)


def test_validate_schema_accepts_valid_schema():
    schema = DocumentSchema(
        name="Invoice",
        description="Invoice metadata",
        fields=[
            SchemaField(name="Invoice Number", field_type="string", required=True),
            SchemaField(name="Total", field_type="number"),
        ],
    )

    result = validate_schema(schema)
    assert result.is_valid
