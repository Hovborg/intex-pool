"""Check links, images, anchors and YAML examples in the maintained guides.

Run from any directory with Python and PyYAML installed. Historical design/audit
documents are valid link targets but are not treated as current user instructions.
"""
from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    "README.md", "info.md", "CONTRIBUTING.md", "SECURITY.md",
    "docs/installation.md", "docs/tuya-setup.md", "docs/dashboard.md",
    "docs/features.md", "docs/troubleshooting.md", "docs/compatibility.md",
    "scripts/browser/README.md", "docs/images/README.md",
]
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)")
HTML_LINK = re.compile(r'(?:src|srcset|href)=[\"\']([^\"\']+)[\"\']')
FENCE = re.compile(r"^```([^\n]*)\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def anchors(content: str) -> set[str]:
    """GitHub-style anchors for the ordinary headings used in these guides."""
    seen: dict[str, int] = {}
    result = set(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', content))
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", content, re.MULTILINE):
        heading = re.sub(r"<[^>]+>", "", unescape(heading)).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
        count = seen.get(slug, 0)
        result.add(f"{slug}-{count}" if count else slug)
        seen[slug] = count + 1
    return result


def main() -> int:
    failures: list[str] = []
    local_links = yaml_examples = images = 0
    for name in GUIDES:
        source = ROOT / name
        if not source.is_file():
            failures.append(f"{name}: missing guide")
            continue
        content = source.read_text(encoding="utf-8")
        prose = FENCE.sub("", content)
        for raw in [*LINK.findall(prose), *HTML_LINK.findall(prose)]:
            url = urlsplit(unescape(raw.strip("<>")))
            if url.scheme or url.netloc:
                continue
            target = (source.parent / unquote(url.path)).resolve() if url.path else source
            local_links += 1
            if not target.is_relative_to(ROOT):
                failures.append(f"{name}: local link leaves repository: {raw}")
                continue
            if not target.exists():
                failures.append(f"{name}: missing link target: {raw}")
                continue
            if (url.fragment and target.suffix == ".md"
                    and unquote(url.fragment) not in anchors(target.read_text(encoding="utf-8"))):
                failures.append(f"{name}: missing heading anchor: {raw}")
            if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
                images += 1
                if target.stat().st_size == 0:
                    failures.append(f"{name}: empty image: {raw}")
        for language, body in FENCE.findall(content):
            if language.strip() in {"yaml", "yml"}:
                yaml_examples += 1
                try:
                    yaml.safe_load(body)
                except yaml.YAMLError as error:
                    failures.append(f"{name}: invalid YAML: {error}")
    if failures:
        print("Documentation checks failed:\n" + "\n".join(f"- {item}" for item in failures))
        return 1
    print(f"PASS: {len(GUIDES)} guides, {local_links} local links/anchors, "
          f"{images} image references, {yaml_examples} YAML examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
