#!/usr/bin/env python3
"""Triage remote V5 ship ports into no-onward-collection vs island-bus work.

This is the layer after remote-port identity audit:

1. Fix suspicious identities first.
2. Confirm ports that do not need onward public-transport collection.
3. Only then collect island bus systems for the remaining ports.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IDENTITY_AUDIT = ROOT / "data" / "v5_remote_port_identity_audit.json"
DEFAULT_OUTPUT = ROOT / "data" / "v5_remote_port_onward_transport_audit.json"
DEFAULT_DOCS_OUTPUT = ROOT / "docs" / "data" / "v5_remote_port_onward_transport_audit.json"
DEFAULT_MARKDOWN = ROOT / "docs" / "v5_remote_port_onward_transport_audit.md"


# These are not "no bus exists" facts.  They are islands/ports where a bus-like
# system is plausible enough that we should search official sources before
# marking the port as terminal-only.
KNOWN_OR_PLAUSIBLE_ISLAND_BUS_HINTS = [
    "西表",
    "竹富",
    "小浜",
    "黒島",
    "波照間",
    "鳩間",
    "座間味",
    "阿嘉",
    "渡嘉敷",
    "粟国",
    "久米",
    "八丈",
    "母島",
    "父島",
    "利島",
    "新島",
    "式根島",
    "神津",
    "三宅",
    "佐渡",
    "隠岐",
    "礼文",
    "利尻",
    "奥尻",
    "奄美",
    "加計呂麻",
    "徳之島",
    "与論",
    "屋久島",
    "種子島",
]

REVIEWED_ONWARD_TRANSPORT_OVERRIDES: dict[str, dict[str, Any]] = {
    "網地港": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Ishinomaki source says Ajishima has a citizen bus; collect the Ajishima bus system"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "石巻市",
                "url": "https://www.city.ishinomaki.lg.jp/cont/10260000/030/20250707144945.html",
                "note": "網地島の紹介 lists 島内交通機関として市民バス.",
            },
        ],
    },
    "大島岡田港": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Oshima Bus source lists route bus service at/around Okada Port; collect Oshima bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "大島バス",
                "url": "https://www.oshima-bus.com/rosen-bus.html",
                "note": "Route bus page lists Okada Port/Motomachi Port connection buses and island bus timetables.",
            },
        ],
    },
    "小値賀柳港": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Ojika/Kyushu passenger-ship sources list Ojika Kotsu access to Yanagi; collect Ojika demand bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "小値賀町",
                "url": "https://www.town.ojika.lg.jp/soshiki/mirai/4/263.html",
                "note": "Town traffic page lists 小値賀交通株式会社 demand service for 小値賀島内.",
            },
            {
                "source": "九州旅客船協会連合会",
                "url": "https://kyushu-ships.com/pages/436/",
                "note": "Passenger-ship access notes list 柳港 via 小値賀交通.",
            },
        ],
    },
    "小値賀大島港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["official town transport page lists ferry access to Oshima, but land bus coverage only for Ojika main island; no Oshima public bus source found"],
        "reviewedStatus": "confirmed_no_public_bus_found",
        "evidence": [
            {
                "source": "小値賀町",
                "url": "https://www.town.ojika.lg.jp/soshiki/mirai/4/263.html",
                "note": "Town page lists 笛吹-大島 as ship service and 小値賀交通 only as 小値賀島内 land transport.",
            },
        ],
    },
    "瀬相": {
        "category": "type1_collect_island_bus",
        "reasons": ["official tourism source says Kakeroma buses wait at Sesou Port; collect Kakeroma Bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "奄美せとうち観光協会",
                "url": "https://www.setouchi-welcome.com/spotinfo/%E5%8A%A0%E8%A8%88%E5%91%82%E9%BA%BB%E3%83%90%E3%82%B9%EF%BC%88%E6%9C%89%EF%BC%89",
                "note": "加計呂麻バス page says buses wait at 瀬相港.",
            },
        ],
    },
    "笛吹": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Ojika/Kyushu passenger-ship sources list Ojika Kotsu access to Fuefuki; collect Ojika demand bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "小値賀町",
                "url": "https://www.town.ojika.lg.jp/soshiki/mirai/4/263.html",
                "note": "Town traffic page lists 小値賀交通株式会社 demand service for 小値賀島内.",
            },
            {
                "source": "九州旅客船協会連合会",
                "url": "https://kyushu-ships.com/pages/436/",
                "note": "Passenger-ship access notes list 笛吹港 via 小値賀交通.",
            },
        ],
    },
    "上五島": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Shinkamigoto source says the town has public route buses; collect Shinkamigoto/Saihi bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "新上五島町",
                "url": "https://official.shinkamigoto.net/goto_kurashi_full.php?eid=00683&r=1",
                "note": "Official town page says 新上五島町 has public route buses operated by Saihi Bus.",
            },
        ],
    },
    "生間": {
        "category": "type1_collect_island_bus",
        "reasons": ["official tourism source says Kakeroma buses wait at Ikenma Port; collect Kakeroma Bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "奄美せとうち観光協会",
                "url": "https://www.setouchi-welcome.com/spotinfo/%E5%8A%A0%E8%A8%88%E5%91%82%E9%BA%BB%E3%83%90%E3%82%B9%EF%BC%88%E6%9C%89%EF%BC%89",
                "note": "加計呂麻バス page says buses wait at 生間港.",
            },
        ],
    },
    "見島本村港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["official/tourism access pages show ship access and mainland access, but no public island bus source was found for Mishima"],
        "reviewedStatus": "confirmed_no_public_bus_found",
        "evidence": [
            {
                "source": "見島観光協会",
                "url": "https://mishimakanko.sakura.ne.jp/access.html",
                "note": "Access page focuses on Hagi-Mishima ship access; no island route-bus source found in official review.",
            },
        ],
    },
    "佐世保柳港": {
        "category": "type1_collect_island_bus",
        "reasons": ["official passenger-ship source lists Ojika Kotsu at Yanagi; collect Ojika demand bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "九州旅客船協会連合会",
                "url": "https://kyushu-ships.com/pages/435/",
                "note": "佐世保市 神浦-寺島-柳 access notes list 柳港 via 小値賀交通.",
            },
        ],
    },
    "青ヶ島三宝港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["official barrier-free terminal record says Aogashima has no bus, taxi, or other land public transport"],
        "reviewedStatus": "confirmed_no_public_transport",
        "evidence": [
            {
                "source": "らくらくおでかけネット",
                "url": "https://www.ecomo-rakuraku.jp/en/station/%E9%9D%92%E3%83%B6%E5%B3%B6%E6%B8%AF%E8%88%B9%E5%AE%A2%E5%BE%85%E5%90%88%E6%89%80/",
                "note": "Terminal page explicitly says 青ヶ島内 has no bus/taxi land public transport.",
            },
        ],
    },
    "友住": {
        "category": "type1_collect_island_bus",
        "reasons": ["official Shinkamigoto source and current bus references show Saihi Bus service through Tomozumi; collect Shinkamigoto/Saihi bus"],
        "reviewedStatus": "official_bus_found",
        "evidence": [
            {
                "source": "新上五島町",
                "url": "https://official.shinkamigoto.net/goto_kurashi_full.php?eid=00683&r=1",
                "note": "Official town page says 新上五島町 has public route buses operated by Saihi Bus.",
            },
        ],
    },
    "硫黄島港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["official Mishima village transport plan says the village has no bus/taxi public transport"],
        "reviewedStatus": "confirmed_no_public_transport",
        "evidence": [
            {
                "source": "三島村地域公共交通総合連携計画",
                "url": "https://mishimamura.com/system/wp-content/uploads/2020/08/renkeikeikaku.pdf",
                "note": "Plan states 三島村内 has no bus/taxi public transport.",
            },
        ],
    },
    "舳倉島港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["official/search review found mainland Wajima bus but no public bus source on Hegurajima; treat as terminal-only until an island transport source appears"],
        "reviewedStatus": "confirmed_no_public_bus_found",
        "evidence": [
            {
                "source": "輪島市/奥能登 route-map review",
                "url": "https://www.hokutetsu.co.jp/_wp/wp-content/uploads/2025/04/okunoto_routemap_202504.pdf",
                "note": "Nearby official bus material covers mainland Wajima/Okunoto routes; no Hegurajima island bus source found.",
            },
        ],
    },
    "飛島勝浦港": {
        "category": "type2_confirmed_no_onward_collection",
        "reasons": ["island profile says Tobishima has no taxi or transport service and movement is on foot or free rental bicycle"],
        "reviewedStatus": "confirmed_no_public_transport",
        "evidence": [
            {
                "source": "SHIMAOMOI",
                "url": "https://shima-omoi.com/research/island.php?id=48",
                "note": "Tobishima profile says there are no taxi/transport services; movement is walking or free rental bicycle.",
            },
        ],
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plausible_bus_hint(port_name: str, operators: list[str]) -> bool:
    text = " ".join([port_name, *operators])
    return any(hint in text for hint in KNOWN_OR_PLAUSIBLE_ISLAND_BUS_HINTS)


def classify(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    port_name = str(row["portName"])
    if port_name in REVIEWED_ONWARD_TRANSPORT_OVERRIDES:
        override = REVIEWED_ONWARD_TRANSPORT_OVERRIDES[port_name]
        return str(override["category"]), list(override["reasons"])
    operators = row.get("operatorContexts") or []
    sailings = int(row.get("playableSailingCount") or 0)
    bus_distance = (row.get("nearestBusStop") or {}).get("distanceMeters")
    rail_distance = (row.get("nearestRail") or {}).get("distanceMeters")

    if row.get("severity") == "needs_identity_review":
        return "identity_review_first", ["port identity or coordinate is not trusted enough for onward triage"]

    if sailings == 0:
        return "type2_no_collection_needed_now", ["not used by current playable ship sailings"]

    if plausible_bus_hint(port_name, operators):
        reasons.append("island/bus hint exists; collect or verify official island bus before terminal-only decision")
        return "type1_collect_island_bus", reasons

    if isinstance(bus_distance, int) and bus_distance <= 10_000:
        reasons.append(f"bus source exists within {bus_distance}m but outside 2km; likely needs local access review")
        return "type1_collect_island_bus", reasons

    if isinstance(rail_distance, int) and rail_distance <= 10_000:
        reasons.append(f"rail exists within {rail_distance}m but outside 2km; likely needs local access review")
        return "type1_collect_island_bus", reasons

    # This is deliberately a candidate bucket.  We still need a source check
    # before permanently marking a playable port as terminal-only.
    if (bus_distance is None or bus_distance > 20_000) and (rail_distance is None or rail_distance > 20_000):
        reasons.append("no known rail/bus source nearby; candidate terminal-only remote port")
        return "type2_candidate_confirm_no_onward_collection", reasons

    reasons.append("remote record, but nearby access signal is ambiguous")
    return "type1_collect_island_bus", reasons


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V5 Remote Port Onward Transport Audit",
        "",
        "This audit applies the gameplay rule that true terminal-only remote ports do",
        "not need bus collection.  It does not collect bus data.  It decides what to",
        "review first.",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: {value}")
    for category in [
        "identity_review_first",
        "type2_no_collection_needed_now",
        "type2_confirmed_no_onward_collection",
        "type2_candidate_confirm_no_onward_collection",
        "type1_collect_island_bus",
    ]:
        lines.extend(["", f"## {category}", ""])
        rows = [row for row in payload["ports"] if row["category"] == category]
        if not rows:
            lines.append("- None.")
            continue
        for row in rows[:80]:
            reason = "; ".join(row["reasons"])
            lines.append(f"- **{row['portName']}** ({row['playableSailingCount']} sailings): {reason}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-audit", type=Path, default=DEFAULT_IDENTITY_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docs-output", type=Path, default=DEFAULT_DOCS_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    identity = read_json(args.identity_audit)
    rows = []
    for source_row in identity.get("ports") or []:
        category, reasons = classify(source_row)
        override = REVIEWED_ONWARD_TRANSPORT_OVERRIDES.get(str(source_row["portName"]))
        rows.append({
            "portName": source_row["portName"],
            "category": category,
            "reasons": reasons,
            "reviewedStatus": override.get("reviewedStatus") if override else None,
            "reviewEvidence": override.get("evidence") if override else [],
            "identitySeverity": source_row.get("severity"),
            "identityReasons": source_row.get("reasons") or [],
            "identityWarnings": source_row.get("warnings") or [],
            "coordinate": source_row.get("coordinate"),
            "operatorContexts": source_row.get("operatorContexts") or [],
            "playableSailingCount": source_row.get("playableSailingCount", 0),
            "nearestRail": source_row.get("nearestRail"),
            "nearestBusStop": source_row.get("nearestBusStop"),
            "sampleSailings": source_row.get("sampleSailings") or [],
            "searchQueries": [
                f"{source_row['portName']} 島内 バス 時刻表 公式",
                f"{source_row['portName']} 港 交通 アクセス 公式",
                f"{source_row['portName']} 公共交通 バス",
            ],
        })

    order = {
        "identity_review_first": 0,
        "type2_no_collection_needed_now": 1,
        "type2_confirmed_no_onward_collection": 2,
        "type2_candidate_confirm_no_onward_collection": 3,
        "type1_collect_island_bus": 4,
    }
    rows.sort(key=lambda row: (order.get(row["category"], 9), -int(row["playableSailingCount"] or 0), row["portName"]))
    counts = Counter(row["category"] for row in rows)
    payload = {
        "schemaVersion": "v5_remote_port_onward_transport_audit_v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceIdentityAudit": str(args.identity_audit.relative_to(ROOT)),
        "summary": {
            "remotePortCount": len(rows),
            "identityReviewFirst": counts.get("identity_review_first", 0),
            "type2NoCollectionNeededNow": counts.get("type2_no_collection_needed_now", 0),
            "type2ConfirmedNoOnwardCollection": counts.get("type2_confirmed_no_onward_collection", 0),
            "type2CandidateConfirmNoOnwardCollection": counts.get("type2_candidate_confirm_no_onward_collection", 0),
            "type1CollectIslandBus": counts.get("type1_collect_island_bus", 0),
        },
        "rules": {
            "identityReviewFirst": "Do not decide terminal-only or bus collection until the port identity/coordinate is fixed.",
            "type2NoCollectionNeededNow": "No current playable sailing uses this port; no bus collection is needed for current gameplay.",
            "type2ConfirmedNoOnwardCollection": "Reviewed online; no ordinary public bus/island land transport needs collection for current gameplay.",
            "type2CandidateConfirmNoOnwardCollection": "Looks like terminal-only remote port, but needs a source check before permanent no-collection classification.",
            "type1CollectIslandBus": "Likely has or needs island/local access bus review after type2 candidates are cleared.",
        },
        "ports": rows,
    }
    write_json(args.output, payload)
    write_json(args.docs_output, payload)
    write_markdown(args.markdown, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(rows[:30], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
