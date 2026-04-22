#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.render_v3_battle_timeline import route_styles
from scripts.dev.run_v3_public_battle_records import DEFAULT_BUNDLE, load_json_maybe_gz, route_title_lookup


INTERNAL_LABEL_RE = re.compile(
    r"\b(?:JR_EAST|SHINKANSEN|TOEI|SG)_[A-Z0-9_]+|\bR_[A-F0-9]{8}\b|\bSG_[A-Z0-9_]+\b|[0-9]+号線",
)
PRIVATE_OPERATOR_PREFIXES = {
    "keikyu": "京急",
    "keio": "京王",
    "keisei": "京成",
    "odakyu": "小田急",
    "seibu": "西武",
    "tobu": "東武",
    "tokyu": "東急",
}
PRIVATE_ALIAS_PREFIXES = {
    "みなとみらい21線": "横浜高速鉄道",
    "小田原線": "小田急",
    "埼玉高速鉄道線": "埼玉高速鉄道",
    "相鉄いずみ野線": "相鉄",
    "相鉄本線": "相鉄",
}


def route_display_issues(bundle_path: Path) -> list[str]:
    bundle = load_json_maybe_gz(bundle_path)
    battle_titles = route_title_lookup(bundle_path)
    timeline_styles = route_styles(bundle)
    issues: list[str] = []
    for route in bundle.get("serviceRoutes", []):
        route_id = str(route.get("id") or "")
        if not route_id:
            continue
        short_name = str(route.get("shortName") or route.get("longName") or route_id)
        battle_title = battle_titles.get(route_id, {}).get("display_name", "")
        timeline_title = timeline_styles.get(route_id).title if route_id in timeline_styles else ""
        for surface, title in (("battle", battle_title), ("timeline", timeline_title)):
            if INTERNAL_LABEL_RE.search(title):
                issues.append(f"{surface}: route {route_id} displays internal label `{title}`")
        expected_prefix = PRIVATE_OPERATOR_PREFIXES.get(str(route.get("operatorId") or ""))
        expected_prefix = PRIVATE_ALIAS_PREFIXES.get(short_name, expected_prefix)
        if expected_prefix:
            for surface, title in (("battle", battle_title), ("timeline", timeline_title)):
                if title and not title.startswith(expected_prefix):
                    issues.append(
                        f"{surface}: private route {route_id} `{short_name}` displays `{title}` without `{expected_prefix}` prefix"
                    )
    return issues


def text_surface_issues(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    for path in paths:
        if path.is_dir():
            files = [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".md", ".html", ".svg"}]
        else:
            files = [path]
        for file_path in files:
            if not file_path.exists():
                issues.append(f"missing text surface: {file_path}")
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            for match in INTERNAL_LABEL_RE.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                issues.append(f"{file_path}:{line_no}: internal label `{match.group(0)}`")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v3 public display names for internal labels and missing private prefixes.")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument(
        "--surface",
        action="append",
        type=Path,
        default=[],
        help="Markdown/HTML/SVG file or directory to scan. Can be repeated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issues = route_display_issues(args.bundle)
    issues.extend(text_surface_issues(args.surface))
    if issues:
        print("v3 display-name audit failed:")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)
    print("v3 display-name audit passed")


if __name__ == "__main__":
    main()
