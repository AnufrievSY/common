from pathlib import Path
from genson import SchemaBuilder
import json
import yaml
import pandas as pd
import orjson

from .utils import has_extension

@has_extension(ext="json")
def json_to_schema(data, file_path: str | Path = "schema.json"):
    """Конвертирует JSON в JSON-схему"""
    builder = SchemaBuilder()
    builder.add_object(data)

    schema = builder.to_schema()

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(str(file_path), "w") as f:
        json.dump(schema, f, indent=2)

@has_extension(ext="json")
def save_json(data: dict | list, file_path: str | Path):
    """Сохраняет данные в JSON файл"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

@has_extension(ext="json", raise_not_found=True)
def read_json(file_path: str | Path) -> dict | list:
    """Читает JSON файл и возвращает данные"""
    return orjson.loads(Path(file_path).read_bytes())

@has_extension(ext="csv")
def save_csv(df: pd.DataFrame, file_path: str | Path) -> None:
    """Сохраняет DataFrame в CSV файл"""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(file_path, sep=';', decimal=',', encoding='utf-8-sig', index=False)

@has_extension(ext="csv", raise_not_found=True)
def read_csv(file_path: str | Path) -> pd.DataFrame:
    """Читает CSV файл и возвращает DataFrame"""
    return pd.read_csv(file_path, sep=';', decimal=',', encoding='utf-8-sig', low_memory=False)

@has_extension(ext="yaml", raise_not_found=True)
def load_yaml(file_path: Path) -> dict:
    """Загружает YAML-файл и возвращает его содержимое как словарь"""
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        raise ValueError(f"Файл {file_path} пуст или повреждён.")
    return data