"""Release-repository consistency checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "ha_delonghi_coffeelink_eletta_explore"


def test_release_metadata_quality_scale_and_workflows_are_consistent() -> None:
    """Prevent stale release claims and floating third-party workflow code."""
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cs = (ROOT / "docs" / "README_CS.md").read_text(encoding="utf-8")

    assert manifest["version"] == "1.2.0"
    assert hacs["homeassistant"] == "2026.8.2"
    assert "Release candidate | 1.2.0" in readme
    assert "Kandidát na vydání | 1.2.0" in readme_cs
    assert len([path for path in (ROOT / "custom_components").iterdir() if path.is_dir()]) == 1

    quality = yaml.safe_load(
        (COMPONENT / "quality_scale.yaml").read_text(encoding="utf-8")
    )["rules"]
    assert {
        "runtime-data",
        "parallel-updates",
        "dynamic-devices",
        "stale-devices",
        "repair-issues",
        "icon-translations",
        "test-coverage",
    } <= quality.keys()

    pinned_action = re.compile(r"^\s*uses:\s+[^@\s]+@[0-9a-f]{40}(?:\s+#.*)?$")
    uses_lines = [
        line
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml")
        for line in workflow.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("uses:")
    ]
    assert uses_lines
    assert all(pinned_action.fullmatch(line) for line in uses_lines)
