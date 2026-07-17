from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def read_result(
    output_path: str | None,
    limit: int = 50,
    *,
    api_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview = _read_output(output_path, limit)
    if not api_result:
        return preview
    result = dict(preview)
    result["apiKind"] = api_result.get("kind", "")
    result["summary"] = api_result.get("counts", api_result.get("summary", {}))
    batch = api_result.get("batch") if isinstance(api_result.get("batch"), dict) else api_result
    result["apiItems"] = batch.get("items", []) if isinstance(batch, dict) else []
    result["apiResult"] = api_result
    if result["kind"] in {"none", "missing"}:
        if api_result.get("kind") == "InfoResult" and api_result.get("preview"):
            rows = api_result["preview"]
            columns = list(rows[0]) if rows else []
            result.update(
                kind="csv",
                title=str(api_result.get("target", "Info")),
                columns=columns,
                rows=[[row.get(column, "") for column in columns] for row in rows],
            )
        else:
            result["kind"] = "api"
            result["title"] = str(api_result.get("operation") or api_result.get("kind", "Result"))
    return result


def _read_output(output_path: str | None, limit: int) -> dict[str, Any]:
    if not output_path:
        return {"kind": "none", "title": "", "items": []}
    path = Path(output_path)
    if path.is_file() and path.suffix.lower() == ".csv":
        return _read_csv(path, limit)
    if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}:
        return {"kind": "images", "title": path.name, "items": [path.as_uri()]}
    if path.is_dir():
        images = sorted(
            item.as_uri()
            for item in path.rglob("*")
            if item.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        if images:
            return {"kind": "images", "title": path.name, "items": images[:100]}
        csv_files = sorted(path.rglob("*.csv"))
        if len(csv_files) == 1:
            return _read_csv(csv_files[0], limit)
        files = sorted(str(item.relative_to(path)) for item in path.rglob("*") if item.is_file())
        return {"kind": "files", "title": path.name, "items": files[:500]}
    return {"kind": "missing", "title": str(path), "items": []}


def _read_csv(path: Path, limit: int) -> dict[str, Any]:
    encodings = ("utf-8-sig", "utf-8", "gb18030")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as stream:
                reader = csv.reader(stream)
                headers = next(reader, [])
                rows = [row for _, row in zip(range(limit), reader, strict=False)]
            return {
                "kind": "csv",
                "title": path.name,
                "columns": headers,
                "rows": rows,
                "items": [],
            }
        except UnicodeDecodeError as exc:
            last_error = exc
    return {"kind": "error", "title": path.name, "error": str(last_error), "items": []}
