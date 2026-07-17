from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from .models import CsvProfile, LogGroupCandidate

_TAG = re.compile(r"\[([^\[\]\r\n]+)\]")
_KEY_VALUE = re.compile(r"([A-Za-z_][\w.-]*)\s*:\s*([^,\s]+)")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(slots=True)
class _LogGroup:
    component: str
    marker: str
    grammar: str
    field_count: int
    columns: tuple[str, ...]
    count: int = 0
    samples: list[str] = field(default_factory=list)
    control_count: int = 0


def analyze_log(
    path: Path,
    *,
    max_lines: int | None = None,
    min_occurrences: int = 3,
    on_progress: Callable[[int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> tuple[LogGroupCandidate, ...]:
    groups: dict[tuple[str, str, str, int], _LogGroup] = {}
    base_counts: dict[tuple[str, str, str], Counter[int]] = defaultdict(Counter)
    base_anomalies: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    base_anomaly_counts: Counter[tuple[str, str, str]] = Counter()
    with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            if line_number % 500 == 0:
                if is_cancelled is not None and is_cancelled():
                    return ()
                if on_progress is not None:
                    on_progress(line_number)
            if max_lines is not None and line_number > max_lines:
                break
            line = raw_line.rstrip("\r\n")
            had_control = bool(_CONTROL.search(line))
            line = _CONTROL.sub("", line)
            tags = list(_TAG.finditer(line))
            if len(tags) < 2:
                continue
            selected: tuple[int, str, tuple[str, tuple[str, ...], int] | None, str] | None = None
            for tag_index in range(len(tags) - 1, 0, -1):
                marker = tags[tag_index].group(1).strip()
                payload = line[tags[tag_index].end() :].strip()
                parsed = _parse_payload(payload, marker)
                grammar = parsed[0] if parsed is not None else _grammar_hint(payload)
                if grammar:
                    selected = (tag_index, payload, parsed, grammar)
                    break
            if selected is None:
                continue
            tag_index, payload, parsed, grammar = selected
            marker = tags[tag_index].group(1).strip()
            component = tags[tag_index - 1].group(1).strip()
            if parsed is None:
                base = (component, marker, grammar)
                base_anomaly_counts[base] += 1
                if len(base_anomalies[base]) < 3:
                    base_anomalies[base].append(line[:800])
                continue
            grammar, columns, field_count = parsed
            base = (component, marker, grammar)
            key = (*base, field_count)
            group = groups.setdefault(
                key, _LogGroup(component, marker, grammar, field_count, columns)
            )
            group.count += 1
            group.control_count += int(had_control)
            if len(group.samples) < 3:
                group.samples.append(line[:800])
            base_counts[base][field_count] += 1

    candidates: list[LogGroupCandidate] = []
    for base, counts in base_counts.items():
        accepted = {width for width, count in counts.items() if count >= min_occurrences}
        for width, _count in counts.items():
            if width not in accepted:
                base_anomalies[base].extend(groups[(*base, width)].samples)
        for width in accepted:
            group = groups[(*base, width)]
            anomaly_count = base_anomaly_counts[base]
            anomaly_count += sum(count for other, count in counts.items() if other not in accepted)
            anomaly_count += group.control_count
            candidates.append(
                LogGroupCandidate(
                    group.component,
                    group.marker,
                    group.grammar,
                    group.field_count,
                    group.count,
                    group.columns,
                    tuple(group.samples),
                    anomaly_count,
                    tuple(base_anomalies[base][:3]),
                )
            )
    filtered: list[LogGroupCandidate] = []
    by_marker: dict[tuple[str, str], list[LogGroupCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_marker[(candidate.component, candidate.marker)].append(candidate)
    for marker_candidates in by_marker.values():
        dominant = max(marker_candidates, key=lambda item: item.count)
        threshold = max(min_occurrences, int(dominant.count * 0.01))
        dropped = [item for item in marker_candidates if item.count < threshold]
        for candidate in marker_candidates:
            if candidate in dropped:
                continue
            if candidate is dominant and dropped:
                candidate = replace(
                    candidate,
                    anomaly_count=candidate.anomaly_count + sum(item.count for item in dropped),
                    anomaly_samples=candidate.anomaly_samples
                    + tuple(sample for item in dropped for sample in item.samples)[:3],
                )
            filtered.append(candidate)
    return tuple(sorted(filtered, key=lambda item: (-item.count, item.marker, item.field_count)))


def _parse_payload(payload: str, marker: str) -> tuple[str, tuple[str, ...], int] | None:
    normalized = payload.lstrip(" ,\t")
    if not normalized:
        return None
    pairs = _KEY_VALUE.findall(normalized)
    if pairs:
        columns = tuple(name for name, _value in pairs)
        return "key_value", columns, len(columns)
    try:
        values = next(csv.reader([normalized], skipinitialspace=True))
    except csv.Error:
        return None
    if len(values) < 2 or not all(_is_number(value) for value in values):
        return None
    columns = tuple(f"{marker.lower()}_{index + 1}" for index in range(len(values)))
    return "numeric", columns, len(values)


def _grammar_hint(payload: str) -> str:
    normalized = payload.lstrip(" ,\t")
    if _KEY_VALUE.search(normalized):
        return "key_value"
    if normalized and (normalized[0].isdigit() or normalized[0] in "+-."):
        return "numeric"
    return ""


def profile_csv(path: Path, *, sample_rows: int = 200) -> CsvProfile:
    encoding = _detect_encoding(path)
    with path.open("r", encoding=encoding, errors="replace", newline="") as stream:
        lines = [stream.readline().rstrip("\r\n") for _ in range(8)]
    lines = [line for line in lines if line != ""]
    if not lines:
        raise ValueError("CSV 文件为空")
    delimiter = _detect_delimiter(lines)
    rows = [next(csv.reader([line], delimiter=delimiter)) for line in lines]
    header_index = _header_index(rows)
    columns = tuple(
        value.strip() or f"column_{index + 1}" for index, value in enumerate(rows[header_index])
    )
    preview: list[tuple[str, ...]] = []
    types: list[Counter[str]] = [Counter() for _ in columns]
    mismatches = 0
    with path.open("r", encoding=encoding, errors="replace", newline="") as stream:
        reader = csv.reader(stream, delimiter=delimiter)
        for row_index, row in enumerate(reader):
            if row_index <= header_index:
                continue
            if len(preview) >= sample_rows:
                break
            if len(row) != len(columns):
                mismatches += 1
                continue
            normalized = tuple(value.strip() for value in row)
            preview.append(normalized)
            for index, value in enumerate(normalized):
                types[index][_value_type(value)] += 1
    column_types = tuple(counter.most_common(1)[0][0] if counter else "text" for counter in types)
    return CsvProfile(
        path.resolve(),
        encoding,
        delimiter,
        header_index if header_index > 0 else 0,
        header_index + 1,
        header_index + 2,
        columns,
        column_types,
        tuple(preview[:20]),
        len(preview),
        mismatches,
    )


def _detect_encoding(path: Path) -> str:
    prefix = path.read_bytes()[:4]
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for encoding in ("utf-8", "gb18030"):
        try:
            path.read_text(encoding=encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _detect_delimiter(lines: list[str]) -> str:
    sample = "\n".join(lines)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {delimiter: max(line.count(delimiter) for line in lines) for delimiter in ",;\t|"}
        return max(counts, key=lambda delimiter: counts[delimiter]) if max(counts.values()) else ","


def _header_index(rows: list[list[str]]) -> int:
    for index, row in enumerate(rows[:5]):
        values = [value.strip() for value in row]
        if (
            len(values) >= 2
            and len(set(values)) == len(values)
            and any(not _is_number(value) for value in values)
        ):
            return index
    return 0


def _value_type(value: str) -> str:
    if not value:
        return "empty"
    try:
        int(value)
        return "integer"
    except ValueError:
        try:
            float(value)
            return "number"
        except ValueError:
            return "text"


def _is_number(value: str) -> bool:
    try:
        float(value.strip())
        return True
    except ValueError:
        return False
