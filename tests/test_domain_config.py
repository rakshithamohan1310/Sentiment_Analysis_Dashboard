"""
Tests for domain YAML config loading.
Uses the real ev.yaml file from config/domains/.
"""
from __future__ import annotations

import pytest

from backend.api.domain_config import (
    _flatten_keywords,
    list_available_domains,
    load_collector_config,
)


def test_ev_domain_config_loads():
    """ev.yaml must exist and parse cleanly."""
    config = load_collector_config("ev")
    assert len(config.keywords) > 0
    assert len(config.subreddits) > 0
    assert config.max_records > 0


def test_ev_domain_has_battery_keywords():
    config = load_collector_config("ev")
    battery_kws = [k.lower() for k in config.keywords]
    assert any("battery" in k for k in battery_kws)


def test_ev_domain_has_charging_keywords():
    config = load_collector_config("ev")
    kws_lower = [k.lower() for k in config.keywords]
    assert any("charging" in k for k in kws_lower)


def test_ev_domain_has_thermal_keywords():
    config = load_collector_config("ev")
    kws_lower = [k.lower() for k in config.keywords]
    assert any("thermal" in k for k in kws_lower)


def test_ev_domain_config_override_keywords():
    """Explicit keywords in overrides replace the YAML defaults."""
    config = load_collector_config("ev", overrides={"keywords": ["custom_kw_only"]})
    assert config.keywords == ["custom_kw_only"]


def test_ev_domain_config_override_max_records():
    config = load_collector_config("ev", overrides={"max_records": 42})
    assert config.max_records == 42


def test_missing_domain_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_collector_config("nonexistent_domain_xyz")


def test_flatten_keywords_deduplicates():
    groups = {
        "a": ["kw1", "kw2"],
        "b": ["kw2", "kw3"],  # kw2 is duplicated across groups
    }
    result = _flatten_keywords(groups)
    assert result.count("kw2") == 1
    assert set(result) == {"kw1", "kw2", "kw3"}


def test_flatten_keywords_preserves_order():
    groups = {"a": ["first", "second"], "b": ["third"]}
    result = _flatten_keywords(groups)
    assert result == ["first", "second", "third"]


def test_list_available_domains_includes_ev():
    domains = list_available_domains()
    assert "ev" in domains


def test_ev_core_code_has_no_ev_hardcoded(tmp_path):
    """
    Sanity check: core pipeline files must not reference 'EV' as a hardcoded string
    in a way that would make them domain-specific.
    Domain names only live in YAML config files and tests.
    """
    import re
    from pathlib import Path

    # Files that are explicitly allowed to mention EV (config, tests, README, data)
    allowed_paths = {"config", "tests", "data", "README"}

    project_root = Path(__file__).resolve().parents[1]
    core_dirs = [project_root / "backend" / "collectors", project_root / "backend" / "api",
                 project_root / "backend" / "models", project_root / "backend" / "database"]

    # Pattern: standalone "EV" as an identifier (not part of "ev.yaml" path references or comments)
    ev_pattern = re.compile(r'\bEV\b')

    violations = []
    for core_dir in core_dirs:
        for py_file in core_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                # Skip comment lines — comments are documentation, not code coupling
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if ev_pattern.search(line):
                    violations.append(f"{py_file.relative_to(project_root)}:{i}: {line.strip()}")

    assert violations == [], (
        "Core pipeline code contains hardcoded 'EV' reference(s):\n" + "\n".join(violations)
    )
