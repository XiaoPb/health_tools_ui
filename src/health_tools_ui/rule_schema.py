from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RuleFieldSchema:
    key: str
    kind: str = "text"
    description: str = ""
    default: Any = ""
    required: bool = False
    choices: tuple[Any, ...] = ()
    children: tuple[RuleFieldSchema, ...] = ()
    item_template: Any = None
    allow_custom_children: bool = False

    def to_choice(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.key,
            "label": self.key,
            "kind": self.kind,
            "description": self.description,
            "defaultValue": self.default,
        }


def _field(key: str, kind: str = "text", default: Any = "", **kwargs: Any) -> RuleFieldSchema:
    return RuleFieldSchema(key, kind, default=default, **kwargs)


CSV_FIELDS = (
    _field("info_row", "integer", 0, description="信息行，0 表示没有信息行"),
    _field("header_row", "integer", 1, required=True, description="列名所在行"),
    _field("data_start_row", "integer", 2, required=True, description="数据起始行"),
    _field("delimiter", "text", ",", description="CSV 分隔符"),
    _field("encoding", "choice", "utf-8", choices=("utf-8", "utf-8-sig", "gb18030")),
    _field("info", "text", ""),
)

ANALYSIS_CAUSE_FIELDS = (
    _field("id", required=True),
    _field("title", required=True),
    _field("origin", "choice", "raw", required=True, choices=("raw", "reference", "algorithm")),
    _field("priority", "integer", 0),
    _field("when", "mapping", {}, required=True, allow_custom_children=True),
    _field("actions", "list", [], item_template=""),
)

RULE_SCHEMAS: dict[str, tuple[RuleFieldSchema, ...]] = {
    "chip": (
        _field("version", default="1.0", required=True),
        _field("chip", required=True),
        _field("csv", "mapping", {}, required=True, children=CSV_FIELDS),
        _field("columns", "list", [], required=True, item_template=""),
        _field("frame_column"),
        _field(
            "acc_columns",
            "mapping",
            {},
            children=tuple(_field(key) for key in ("x", "y", "z")),
        ),
        _field("check_columns", "mapping", {}, allow_custom_children=True),
        _field("factory_columns", "list", [], item_template=""),
        _field("factory_config", "mapping", {}, allow_custom_children=True),
        _field("gain_tia_map", "mapping", {}, allow_custom_children=True),
        _field("chip_info", "mapping", {}, allow_custom_children=True),
        _field("hr_ref_column", "mapping", {}, allow_custom_children=True),
        _field("spo_ref_column", "mapping", {}, allow_custom_children=True),
    ),
    "parse": (
        _field("version", default="1.0", required=True),
        _field("description"),
        _field("chip"),
        _field("target_chip"),
        _field("regex", "regex", ""),
        _field("columns", "list", [], item_template=""),
        _field("separator", default=","),
        _field(
            "patterns",
            "mapping",
            {},
            allow_custom_children=True,
            item_template={"regex": "", "columns": [], "separator": ","},
        ),
    ),
    "patterns": (
        _field("version", default="1.0", required=True),
        _field("description"),
        _field(
            "patterns",
            "mapping",
            {},
            required=True,
            allow_custom_children=True,
            item_template=[],
        ),
    ),
    "classify": (
        _field("version", default="1.0", required=True),
        _field("description"),
        _field("extends"),
        _field("target_chip"),
        _field("filename", "mapping", {}, allow_custom_children=True),
        _field(
            "data_columns",
            "list",
            [],
            item_template={"name": "", "source": "data", "type": "string"},
        ),
        _field("structure", "mapping", {}, allow_custom_children=True),
        _field("rules", "list", [], item_template={"target": "", "use_filename": True}),
        _field("extract", "list", [], item_template={"name": "", "function": "", "params": {}}),
        _field("classify", "list", [], item_template={"target": "", "condition": ""}),
        _field("accuracy", "mapping", {}, allow_custom_children=True),
        _field("default", default="unclassified"),
        _field("patterns", "mapping", {}, allow_custom_children=True),
    ),
    "convert": (
        _field("version", default="1.0", required=True),
        _field("description"),
        _field("target_chip"),
        _field("csv", "mapping", {}, children=CSV_FIELDS),
        _field("source_columns", "list", [], item_template=""),
        _field("target_columns", "list", [], item_template=""),
        _field("column_mapping", "mapping", {}, allow_custom_children=True),
        _field("computed", "mapping", {}, allow_custom_children=True),
        _field("forward_fill", "list", [], item_template=""),
        _field("expand_repeat", "mapping", {}, allow_custom_children=True),
        _field(
            "extra_source",
            "list",
            [],
            item_template={"name": "", "pattern": "*.csv", "column_mapping": {}},
        ),
    ),
    "evaluate": (
        _field("description"),
        _field("type", "choice", "hr", required=True, choices=("hr", "spo2")),
        _field("ref_column", default="REF_RESULT0", required=True),
        _field("pred_column", default="ALGO_RESULT0", required=True),
        _field("anomaly", "mapping", {}, allow_custom_children=True),
        _field("classify", "mapping", {}, allow_custom_children=True),
        _field("classify_rule"),
        _field("methods", "list", [], item_template="mae"),
        _field("thresholds", "list", [], item_template={"name": "", "value": 0}),
        _field("first_output_time", "boolean", False),
        _field("default_category", default="other"),
    ),
    "analysis": (
        _field("version", default="1.0", required=True),
        _field("type", "choice", "hr", required=True, choices=("hr", "spo2", "other")),
        _field("description"),
        _field(
            "columns",
            "mapping",
            {},
            required=True,
            children=(
                _field("reference"),
                _field("prediction"),
                _field("timestamp"),
                _field("ppg_patterns", "list", [], item_template=""),
                _field("acc", "list", [], item_template=""),
            ),
            allow_custom_children=True,
        ),
        _field("detectors", "list", [], required=True, item_template="integrity"),
        _field(
            "sampling",
            "mapping",
            {},
            children=(
                _field("sample_rate", "number", 25),
                _field(
                    "infer_timestamp_unit",
                    "choice",
                    "auto",
                    choices=("auto", "s", "ms", "us"),
                ),
            ),
            allow_custom_children=True,
        ),
        _field("thresholds", "mapping", {}, allow_custom_children=True),
        _field(
            "offline",
            "mapping",
            {},
            children=(_field("enabled", "boolean", True),),
            allow_custom_children=True,
        ),
        _field(
            "causes",
            "list",
            [],
            required=True,
            children=ANALYSIS_CAUSE_FIELDS,
            item_template={
                "id": "new_cause",
                "title": "新分析原因",
                "origin": "raw",
                "priority": 0,
                "when": {"feature": "data_complete", "op": "eq", "value": False},
            },
        ),
    ),
    "config": (
        _field("rules_dir", "path"),
        _field("offline_tools_path", "path"),
        _field("offline_versions", "mapping", {}, allow_custom_children=True),
        _field("offline_cmd", "mapping", {}, allow_custom_children=True),
    ),
}


class RuleSchemaRegistry:
    @staticmethod
    def fields(kind: str, variant: str | None = None) -> tuple[RuleFieldSchema, ...]:
        return RULE_SCHEMAS.get(variant or kind, ())

    @classmethod
    def available_children(
        cls, kind: str, pointer: str, existing: set[str], variant: str | None = None
    ) -> list[RuleFieldSchema]:
        fields = cls.fields(kind, variant)
        for token in _tokens(pointer):
            if token.isdigit():
                continue
            match = next((item for item in fields if item.key == token), None)
            if match is None:
                return []
            fields = match.children
        return [item for item in fields if item.key not in existing]

    @classmethod
    def schema_at(
        cls, kind: str, pointer: str, variant: str | None = None
    ) -> RuleFieldSchema | None:
        fields = cls.fields(kind, variant)
        current: RuleFieldSchema | None = None
        for token in _tokens(pointer):
            if token.isdigit():
                continue
            current = next((item for item in fields if item.key == token), None)
            if current is None:
                return None
            fields = current.children
        return current


def _tokens(pointer: str) -> list[str]:
    return [token for token in pointer.strip("/").split("/") if token]
