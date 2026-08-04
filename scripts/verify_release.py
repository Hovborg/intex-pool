#!/usr/bin/env python3
"""Verify release versions and generated dashboard-card artefacts agree."""
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD_BANNER = re.compile(r"^// intex-pool-card v(?P<version>[^\s]+)$", re.MULTILINE)


def _json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def release_versions(root: Path = ROOT) -> dict[str, str | None]:
    """Return every independently stored release version."""
    manifest = _json(root / "custom_components/intex_pool/manifest.json")
    with (root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    package = _json(root / "card/package.json")
    lockfile = _json(root / "card/package-lock.json")
    bundle = (root / "custom_components/intex_pool/frontend/intex-pool-card.js").read_text(
        encoding="utf-8"
    )
    bundle_match = CARD_BANNER.search(bundle)
    return {
        "manifest": manifest.get("version"),
        "pyproject": pyproject.get("project", {}).get("version"),
        "card/package.json": package.get("version"),
        "card/package-lock.json": lockfile.get("version"),
        "card/package-lock.json packages['']": lockfile.get("packages", {})
        .get("", {})
        .get("version"),
        "card bundle": bundle_match.group("version") if bundle_match else None,
    }


def verify_release(root: Path = ROOT) -> list[str]:
    """Return human-readable consistency failures, or an empty list."""
    versions = release_versions(root)
    expected = versions["manifest"]
    failures = [
        f"{source}: expected {expected!r}, found {version!r}"
        for source, version in versions.items()
        if version != expected
    ]
    source_map = root / "custom_components/intex_pool/frontend/intex-pool-card.js.map"
    if not source_map.is_file():
        failures.append(f"missing generated source map: {source_map.relative_to(root)}")
    return failures


def main() -> int:
    failures = verify_release()
    if failures:
        print("Release consistency check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    version = release_versions()["manifest"]
    print(f"Release metadata and card artefacts agree on v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
