from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from health_tools.api import (
    ClassifyRequest,
    ConvertRequest,
    EvaluateRequest,
    ExecutionContext,
    ParseRequest,
    run_classify,
    run_convert,
    run_evaluate,
    run_parse,
)

from .models import RuleDraft


class RulePreviewSession:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="health-tools-ui-preview-"))

    def run(
        self,
        draft: RuleDraft,
        input_path: Path,
        *,
        context: ExecutionContext | None = None,
    ):
        rule_path = self.root / draft.kind / draft.name
        rule_path.parent.mkdir(parents=True, exist_ok=True)
        rule_path.write_text(draft.source, encoding="utf-8")
        output = self.root / "output"
        output.mkdir(exist_ok=True)
        if draft.kind == "parse":
            return run_parse(ParseRequest(input_path, output, str(rule_path)), context=context)
        if draft.kind == "convert":
            return run_convert(
                ConvertRequest(input_path, output / "preview.csv", str(rule_path)),
                context=context,
            )
        if draft.kind == "classify":
            return run_classify(
                ClassifyRequest(input_path, output, str(rule_path), mode="copy"), context=context
            )
        if draft.kind == "evaluate":
            source = input_path.parent if input_path.is_file() else input_path
            filter_name = input_path.name if input_path.is_file() else None
            return run_evaluate(
                EvaluateRequest(
                    source,
                    output,
                    rule_file=str(rule_path),
                    filter_name=filter_name,
                ),
                context=context,
            )
        raise ValueError(f"{draft.kind} 不支持运行预览")

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> RulePreviewSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.cleanup()
