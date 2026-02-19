from pathlib import Path
from genson import SchemaBuilder
import json

def json_to_schema(data, file_path: str | Path = "schema.json"):
    """Конвертирует JSON в JSON-схему"""
    builder = SchemaBuilder()
    builder.add_object(data)

    schema = builder.to_schema()

    with open(str(file_path), "w") as f:
        json.dump(schema, f, indent=2)

