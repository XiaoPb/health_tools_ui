from __future__ import annotations

from pathlib import Path

from health_tools_ui.resources import OfflineCatalogService, RuleCatalogService


def _write(path: Path, source: str = "version: '1.0'\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_rule_catalog_prefers_user_rules_and_detects_patterns(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    config = tmp_path / "config.yaml"
    _write(builtin / "chip" / "gh3220.yaml", "chip: gh3220\n")
    _write(builtin / "convert" / "standard.yaml")
    _write(user / "convert" / "standard.yaml", "description: custom\n")
    _write(user / "classify" / "patterns.yaml", "patterns:\n  sit: [sit]\n")
    config.write_text(f"rules_dir: '{user.as_posix()}'\n", encoding="utf-8")

    service = RuleCatalogService(
        auto_initialize=False,
        config_file=config,
        default_rules_dir=user,
        builtin_rules_dir=builtin,
    )

    convert = service.choices("convert")
    assert len(convert) == 1
    assert convert[0]["source"] == "user"
    assert convert[0]["overrides_builtin"] is True
    patterns = service.choices("classify", patterns_only=True)
    assert [item["value"] for item in patterns] == ["patterns.yaml"]
    assert service.choices("chip")[0]["value"] == "gh3220"


def test_rule_destination_rejects_directory_traversal(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin"
    user = tmp_path / "user"
    user.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(f"rules_dir: '{user.as_posix()}'\n", encoding="utf-8")
    service = RuleCatalogService(
        auto_initialize=False,
        config_file=config,
        default_rules_dir=user,
        builtin_rules_dir=builtin,
    )
    assert service.destination("parse", "custom").name == "custom.yaml"
    try:
        service.destination("parse", "../escape")
    except ValueError as exc:
        assert "文件名" in str(exc)
    else:
        raise AssertionError("directory traversal was accepted")


def test_offline_catalog_supports_grouped_legacy_and_missing_versions(tmp_path: Path) -> None:
    config = {
        "offline_versions": {
            "gh3220": {
                "versions": {"exclusive": ["v2", "v1", "v2"], "medium": ["m1"]},
                "default": "v2",
            },
            "legacy": {"versions": ["old"]},
        }
    }
    service = OfflineCatalogService(
        lambda: config,
        lambda _chip, version: tmp_path / "TEE_Algorithm.exe" if version == "v2" else None,
    )
    versions = service.versions("gh3220")
    assert [item["value"] for item in versions] == ["v2", "v1", "m1"]
    assert versions[0]["isDefault"] is True
    assert versions[1]["enabled"] is False
    assert service.versions("gh3220", allow_missing=True)[1]["enabled"] is True
    assert service.versions("legacy", allow_missing=True)[0]["category"] == "exclusive"
