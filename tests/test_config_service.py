from __future__ import annotations

from pathlib import Path

from health_tools_ui.config_service import HealthConfigService


def test_user_config_has_priority_and_syncs_to_install_dir(tmp_path: Path) -> None:
    user = tmp_path / "user" / "config.yaml"
    install = tmp_path / "install" / "config" / "config.yaml"
    user.parent.mkdir()
    install.parent.mkdir(parents=True)
    user.write_bytes(b"rules_dir: user\r\n")
    install.write_text("rules_dir: install\n", encoding="utf-8")

    service = HealthConfigService(user, install)
    assert service.initialize_and_sync() == user
    assert install.read_bytes() == b"rules_dir: user\r\n"


def test_install_copy_restores_missing_user_config(tmp_path: Path) -> None:
    user = tmp_path / "user" / "config.yaml"
    install = tmp_path / "install" / "config.yaml"
    install.parent.mkdir(parents=True)
    install.write_text("rules_dir: restored\n", encoding="utf-8")

    service = HealthConfigService(user, install)
    service.initialize_and_sync()
    assert user.read_text(encoding="utf-8") == "rules_dir: restored\n"


def test_save_updates_both_config_copies(tmp_path: Path) -> None:
    user = tmp_path / "user" / "config.yaml"
    install = tmp_path / "install" / "config.yaml"
    service = HealthConfigService(user, install)
    service.save("rules_dir: changed\n")
    assert user.read_text(encoding="utf-8") == install.read_text(encoding="utf-8")
