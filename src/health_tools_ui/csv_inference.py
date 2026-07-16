from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InferredColumns:
    columns: tuple[str, ...]
    row: int
    encoding: str


def infer_csv_columns(path: Path) -> InferredColumns | None:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                rows = []
                reader = csv.reader(stream)
                for _index in range(2):
                    rows.append(next(reader, []))
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
        for row_number, row in enumerate(rows, 1):
            columns = tuple(item.strip() for item in row)
            if _valid_columns(columns):
                return InferredColumns(columns, row_number, encoding)
    return None


def _valid_columns(columns: tuple[str, ...]) -> bool:
    nonempty = [column for column in columns if column]
    return len(nonempty) >= 2 and len(nonempty) == len(columns)
