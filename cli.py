import click
import json
from utils.preprocess import preprocess
from utils.schema_manager import SchemaManager
from utils.classifier import classify
from utils.extractor import extract


@click.command()
@click.argument("file", type=click.File("rb"))
@click.option("--types", multiple=True, help="Candidate document types")
@click.option("--custom-schema", type=click.File("r"), help="JSON custom schema file")
def main(file, types, custom_schema):
    """CLI: classify and extract metadata from document"""
    sm = SchemaManager()
    if custom_schema:
        sm.add_custom(json.load(custom_schema))
    text, _ = preprocess(file)
    if not types:
        types = sm.get_types()
    cls = classify(text, types)
    schema = sm.get(cls["doc_type"])
    extr = extract(text, schema)
    result = {"classification": cls, "extraction": extr}
    click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
