import datetime
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketContext:
    shop_name: str
    headers: dict[str, str]
    performance_data: Optional[dict[str, str]] = None

@dataclass(frozen=True)
class ReturnsBarcode:
    data: dict[str, str]
    barcode: Path

@dataclass(frozen=True)
class ReturnsReport:
    title: str
    date: datetime.datetime
    town: Optional[Literal['ЕКБ', 'МСК']]
    file_path: Path

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'date': self.date,
            'town': self.town,
            'file_path': str(self.file_path)
        }