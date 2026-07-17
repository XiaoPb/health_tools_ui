from __future__ import annotations

from pathlib import Path

from health_tools.api import (
    OfflineCatalogResult,
    OfflineVersionInfo,
    RuleCatalogResult,
    RuleDocumentResult,
    RuleInfo,
    RuleSource,
    RuleType,
    RuleVariantInfo,
)

from health_tools_ui.resources import OfflineCatalogService, RuleCatalogService


def test_rule_catalog_uses_public_rule_metadata_and_detects_patterns(qapp, tmp_path: Path) -> None:
    path = tmp_path / "classify" / "patterns.yaml"
    variant = RuleVariantInfo(RuleSource.USER, path, True, "r1")
    info = RuleInfo(RuleType.CLASSIFY, path.name, RuleSource.USER, path, True, True, (variant,))

    service = RuleCatalogService(
        list_runner=lambda _request: RuleCatalogResult((info,)),
        read_runner=lambda _request: RuleDocumentResult(info, "patterns:\n  sit: [sit]\n", "r1"),
    )
    choices = service.choices("classify", patterns_only=True)
    assert choices[0]["value"] == "patterns.yaml"
    assert choices[0]["overrides_builtin"] is True


def test_offline_catalog_maps_public_versions() -> None:
    result = OfflineCatalogResult(
        (
            OfflineVersionInfo("gh3220", "exclusive", "v2", True, True),
            OfflineVersionInfo("gh3220", "exclusive", "v1", False, False),
        )
    )
    service = OfflineCatalogService(lambda _request: result)
    versions = service.versions("gh3220")
    assert [item["value"] for item in versions] == ["v2", "v1"]
    assert versions[0]["isDefault"] is True
    assert versions[1]["enabled"] is False
    assert service.versions("gh3220", allow_missing=True)[1]["enabled"] is True
