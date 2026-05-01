#!/usr/bin/env python3
"""Audit numbered named trains for likely missing limited-express services.

The audit is heuristic: real timetables can skip numbers, split service families
by operating day, or use special numbering blocks.  It is meant to surface
review candidates like the Tsuruga-origin Thunderbird gap, where one origin and
terminal should expose a dense even/odd number sequence but many train numbers
are absent.  It also checks the boarding-station view so pass-through trains do
not look missing just because their true origin is farther upstream.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "v4_current_weekday_train_instances.json.gz"
DEFAULT_OUTPUT = ROOT / "data" / "v4_limited_express_number_gap_audit.json"

NUMBERED_NAME_RE = re.compile(r"^\s*(?P<family>.+?)\s*(?P<number>\d{1,4})\s*号(?:\D|$)")
LEADING_TYPE_RE = re.compile(r"^(?:特急|急行|快速特急|快特|普通|快速|新快速|区間快速|通勤快速|直通快速)\s*")
ROUTE_LIKE_RE = re.compile(r"(?:線|本線|号線|ライン|Line|モノレール|アストラムライン)$", re.I)
EXCLUDED_FAMILY_RE = re.compile(
    r"(?:快速|新快速|区間快速|通勤快速|直通快速|普通|各停|ライナー|号線|モノレール|アストラムライン|アンパンマントロッコ)"
)
SHINKANSEN_FAMILIES = {
    "のぞみ", "ひかり", "こだま", "みずほ", "さくら", "つばめ",
    "はやぶさ", "やまびこ", "なすの", "こまち", "つばさ",
    "とき", "たにがわ", "かがやき", "はくたか", "あさま", "つるぎ",
}
KNOWN_LIMITED_EXPRESS_FAMILIES = {
    "あずさ", "かいじ", "富士回遊", "ひたち", "ときわ", "踊り子", "サフィール踊り子",
    "湘南", "成田エクスプレス", "草津・四万", "あかぎ",
    "サンダーバード", "しらさぎ", "くろしお", "こうのとり", "きのさき", "はしだて",
    "まいづる", "やくも", "スーパーはくと", "スーパーいなば", "はまかぜ",
    "しなの", "ひだ", "南紀", "ふじかわ", "伊那路",
    "ソニック", "リレーかもめ", "みどり", "ハウステンボス", "かささぎ",
    "にちりん", "にちりんシーガイア", "ひゅうが", "きりしま", "きらめき",
    "ゆふ", "ゆふいんの森", "あそぼーい！", "九州横断特急", "かいおう",
    "南風", "しおかぜ", "いしづち", "うずしお", "宇和海", "あしずり",
    "しまんと", "剣山", "スーパーおき", "スーパーまつかぜ",
    "りょうもう", "リバティりょうもう", "けごん", "リバティけごん",
    "きぬ", "リバティきぬ", "リバティ会津", "スペーシアＸ",
    "はこね", "さがみ", "えのしま", "ふじさん", "モーニングウェイ",
    "ホームウェイ", "メトロはこね", "メトロホームウェイ",
}

REVIEWED_GAP_PATTERNS = {
    ("成田エクスプレス", "大船", "成田空港"): {
        "category": "alternate_origin_pattern",
        "note": "Numbers in the missing-looking block are present as Shinjuku-origin NEX services; Ofuna-origin NEX uses a separate numbering cadence.",
        "source": "JR East official 2026-05 timetable",
    },
    ("ときわ", "品川", "勝田"): {
        "category": "official_numbering_gap",
        "note": "Current JR East Shinagawa Joban Line timetable skips this late-evening block; 95 is Ueno-origin and 97 resumes Shinagawa-origin service.",
        "source": "JR East official 2026-05 timetable",
    },
    ("あずさ", "東京", "松本"): {
        "category": "official_numbering_gap",
        "note": "Tokyo-origin evening Azusa services run as 41, 45, 49, 53, and 55 in the official JR East timetable.",
        "source": "JR East official 2026-05 timetable",
    },
    ("あずさ", "松本", "東京"): {
        "category": "official_numbering_gap",
        "note": "Matsumoto-to-Tokyo morning Azusa services use a sparse even-number cadence in the official JR East timetable.",
        "source": "JR East official 2026-05 timetable",
    },
    ("こうのとり", "城崎温泉", "新大阪"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking numbers 16, 20, and 24 are present as Fukuchiyama-origin Kounotori services.",
        "source": "JR West official weekday timetable",
    },
    ("富士回遊", "大月", "河口湖"): {
        "category": "official_numbering_gap",
        "note": "Fuji Kaiyu through services at Otsuki use 3, 7, 11, and 15 in the official JR East weekday timetable.",
        "source": "JR East official 2026-05 timetable",
    },
    ("スペーシアＸ", "東武日光", "浅草"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 8号 and 10号 are current Spacia X services from Kinugawa-onsen, not Tobu-nikko-origin services.",
        "source": "Tobu Railway official Spacia X timetable",
    },
    ("にちりん", "大分", "宮崎空港"): {
        "category": "parallel_family_numbering",
        "note": "The apparent 5号 gap is occupied by にちりんシーガイア5号 in the current timetable rather than plain にちりん5号.",
        "source": "JR Kyushu current timetable",
    },
    ("はこね", "小田原", "町田"): {
        "category": "holiday_only_pattern",
        "note": "Public stop tables for the missing-looking 24号, 26号, and 28号 mark them as Saturday/holiday Hakone services; the current v4 collection is weekday.",
        "source": "Public Odakyu Romancecar stop tables, 2026-03-14 revision",
    },
    ("きのさき", "城崎温泉", "京都"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 14号 is present as a Fukuchiyama-origin Kinosaki service.",
        "source": "JR West official weekday timetable",
    },
    ("ときわ", "高萩", "品川"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 62号 is present as a Katsuta-origin Tokiwa service.",
        "source": "JR East official 2026-05 timetable",
    },
    ("わかしお", "安房鴨川", "東京"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 10号 is present as a Katsuura-origin Wakashio service.",
        "source": "JR East official 2026-05 timetable",
    },
    ("スーパーはくと", "倉吉", "大阪"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 6号 is present as a Tottori-origin Super Hakuto service.",
        "source": "JR West official weekday timetable",
    },
    ("スーパーまつかぜ", "益田", "鳥取"): {
        "category": "alternate_origin_pattern",
        "note": "Missing-looking 8号 is present as a Yonago-origin Super Matsukaze service.",
        "source": "JR West official weekday timetable",
    },
}

REVIEWED_GAP_PATTERNS.update(
    {
        ("くろしお", "白浜", "新大阪"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking even numbers are present as Shingu-origin Kuroshio services passing Shirahama.",
            "source": "JR West official weekday timetable",
        },
        ("こうのとり", "福知山", "新大阪"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking numbers 12, 14, 18, and 22 are present as Kinosaki-onsen-origin Kounotori services passing Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("こうのとり", "新大阪", "福知山"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking numbers 9, 13, and 17 are present from Shin-Osaka but continue beyond Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("こうのとり", "新大阪", "城崎温泉"): {
            "category": "short_turn_pattern",
            "note": "Missing-looking numbers 7 and 11 are present from Shin-Osaka but terminate at Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("ときわ", "勝田", "品川"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking numbers 56, 58, 60, and 64 are present as Takahagi-origin Tokiwa services passing Katsuta.",
            "source": "JR East official 2026-05 timetable",
        },
        ("はるか", "京都", "関西空港"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking numbers 3, 9, and 11 are present as Kusatsu/Yasu-origin Haruka services passing Kyoto.",
            "source": "JR West official weekday timetable",
        },
        ("はるか", "関西空港", "京都"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking numbers 50 and 54 are present from Kansai-airport but continue beyond Kyoto to Yasu.",
            "source": "JR West official weekday timetable",
        },
        ("きのさき", "福知山", "京都"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking numbers 8 and 12 are present as Toyooka- or Kinosaki-onsen-origin Kinosaki services passing Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("きのさき", "京都", "福知山"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking numbers 5, 7, 9, and 15 are present from Kyoto but continue beyond Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("きのさき", "京都", "城崎温泉"): {
            "category": "short_turn_pattern",
            "note": "Missing-looking 3号 is present from Kyoto but terminates at Fukuchiyama.",
            "source": "JR West official weekday timetable",
        },
        ("ひたち", "いわき", "品川"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking numbers 12 and 22 are present as Sendai-origin Hitachi services passing Iwaki.",
            "source": "JR East official 2026-05 timetable",
        },
        ("ひたち", "品川", "いわき"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking numbers 3, 13, and 21 are present from Shinagawa but continue beyond Iwaki to Sendai.",
            "source": "JR East official 2026-05 timetable",
        },
        ("成田エクスプレス", "成田空港", "大船"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking even numbers are present as Narita-airport-origin NEX services terminating at Shinjuku instead of Ofuna.",
            "source": "JR East official 2026-05 timetable",
        },
        ("いなほ", "酒田", "新潟"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking 8号 is present as an Akita-origin Inaho service passing Sakata.",
            "source": "JR East official 2026-05 timetable",
        },
        ("いなほ", "新潟", "酒田"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking 7号 is present from Niigata but continues beyond Sakata to Akita.",
            "source": "JR East official 2026-05 timetable",
        },
        ("湘南", "東京", "小田原"): {
            "category": "branch_destination_pattern",
            "note": "Missing-looking numbers 5 and 17 are present from Tokyo but terminate at Hiratsuka rather than Odawara.",
            "source": "JR East official 2026-05 timetable",
        },
        ("スペーシアＸ", "浅草", "東武日光"): {
            "category": "branch_destination_pattern",
            "note": "Missing-looking 7号 and 9号 are current Spacia X services from Asakusa to Kinugawa-onsen, not Tobu-nikko-bound services.",
            "source": "Tobu Railway official Spacia X timetable",
        },
        ("ソニック", "大分", "博多"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking 12号 is present as a Saiki-origin Sonic service passing Oita.",
            "source": "NAVITIME/JR Kyushu weekday timetable",
        },
        ("ソニック", "博多", "大分"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking 41号 is present from Hakata but continues beyond Oita to Saiki.",
            "source": "NAVITIME/JR Kyushu weekday timetable",
        },
        ("ひゅうが", "延岡", "宮崎空港"): {
            "category": "short_turn_pattern",
            "note": "Missing-looking 3号 is present from Nobeoka but terminates at Miyazaki instead of Miyazaki-airport.",
            "source": "NAVITIME/JR Kyushu weekday timetable",
        },
        ("あしずり", "中村", "高知"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking 6号 is present as a Sukumo-origin Ashizuri service passing Nakamura.",
            "source": "NAVITIME/JR Shikoku weekday timetable",
        },
        ("あしずり", "高知", "中村"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking 7号 is present from Kochi but continues beyond Nakamura to Sukumo.",
            "source": "NAVITIME/JR Shikoku weekday timetable",
        },
        ("スーパーまつかぜ", "鳥取", "益田"): {
            "category": "short_turn_pattern",
            "note": "Missing-looking 3号 is present from Tottori but terminates at Yonago.",
            "source": "JR West official weekday timetable",
        },
        ("ひだ", "高山", "名古屋"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking 12号 is present as a Hida-Furukawa-origin Hida service passing Takayama.",
            "source": "NAVITIME/JR Central weekday timetable",
        },
        ("ひだ", "名古屋", "富山"): {
            "category": "branch_destination_pattern",
            "note": "Missing-looking 5号 and 9号 are present from Nagoya but terminate at Hida-Furukawa/Takayama rather than Toyama.",
            "source": "JR West/NAVITIME weekday timetable",
        },
        ("ひだ", "名古屋", "高山"): {
            "category": "alternate_terminal_pattern",
            "note": "Missing-looking 5号 is present from Nagoya but continues beyond Takayama to Hida-Furukawa.",
            "source": "JR West/NAVITIME weekday timetable",
        },
        ("メトロホームウェイ", "大手町", "本厚木"): {
            "category": "alternate_origin_pattern",
            "note": "Missing-looking 43号 is present as a Metro Homeway through service whose full origin is Kita-senju.",
            "source": "v3 Odakyu/Tokyo Metro source snapshot",
        },
        ("ホームウェイ", "新宿", "秦野"): {
            "category": "branch_destination_pattern",
            "note": "Missing-looking 5号 is present from Shinjuku but continues beyond Hadano to Odawara.",
            "source": "v3 Odakyu source snapshot",
        },
    }
)


def load_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def clean_family(value: str) -> str:
    family = LEADING_TYPE_RE.sub("", value)
    family = re.sub(r"\s+", "", family)
    family = family.strip("　 |:：・-")
    return family


def numbered_family(train: dict[str, Any]) -> tuple[str, int] | None:
    candidates = [
        train.get("display_name"),
        train.get("service_name_detail"),
        train.get("route_name"),
        train.get("service_name"),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text:
            continue
        match = NUMBERED_NAME_RE.search(text)
        if not match:
            continue
        family = clean_family(match.group("family"))
        if not family:
            continue
        if ROUTE_LIKE_RE.search(family) or EXCLUDED_FAMILY_RE.search(family):
            continue
        return family, int(match.group("number"))
    return None


def is_limited_express_like(train: dict[str, Any], family: str, include_shinkansen: bool) -> bool:
    if family in SHINKANSEN_FAMILIES:
        return include_shinkansen
    train_type = str(train.get("train_type") or "")
    if "特急" in train_type:
        return True
    if family in KNOWN_LIMITED_EXPRESS_FAMILIES:
        return True
    service_text = " ".join(str(train.get(key) or "") for key in ("display_name", "service_name_detail", "route_name"))
    return "特急" in service_text and family not in SHINKANSEN_FAMILIES


def stop_name(stop: dict[str, Any] | None) -> str:
    stop = stop or {}
    return str(stop.get("station_name_raw") or stop.get("station_name") or stop.get("station_group_id") or "")


def stop_group_id(stop: dict[str, Any] | None) -> str:
    stop = stop or {}
    return str(stop.get("station_group_id") or stop.get("station_id") or "")


def stop_time(stop: dict[str, Any] | None) -> str:
    stop = stop or {}
    return str(stop.get("departure_hhmm") or stop.get("arrival_hhmm") or "")


def expected_numbers(numbers: list[int], step: int) -> list[int]:
    if not numbers:
        return []
    return list(range(min(numbers), max(numbers) + 1, step))


def sequence_step(numbers: list[int]) -> int | None:
    unique = sorted(set(numbers))
    if len(unique) < 4:
        return None
    if all(number % 2 == unique[0] % 2 for number in unique):
        return 2
    return 1


def summarize_group(
    key: tuple[str, str, str],
    items: list[dict[str, Any]],
    *,
    family_numbers: dict[str, set[int]],
    family_origin_numbers: dict[tuple[str, str], set[int]],
    family_station_numbers: dict[tuple[str, str], set[int]],
) -> dict[str, Any] | None:
    family, origin, terminal = key
    numbers = sorted({int(item["number"]) for item in items})
    step = sequence_step(numbers)
    if not step:
        return None
    expected = expected_numbers(numbers, step)
    missing = [number for number in expected if number not in numbers]
    if not missing:
        return None
    missing_unseen_from_origin = [
        number for number in missing
        if number not in family_origin_numbers.get((family, origin), set())
    ]
    missing_unseen_at_boarding_station = [
        number for number in missing
        if number not in family_station_numbers.get((family, origin), set())
    ]
    missing_unseen_globally = [
        number for number in missing
        if number not in family_numbers.get(family, set())
    ]
    density = len(numbers) / len(expected) if expected else 0
    gap_ratio = len(missing) / len(expected) if expected else 0
    return {
        "serviceFamily": family,
        "origin": origin,
        "terminal": terminal,
        "observedCount": len(numbers),
        "observedNumbers": numbers,
        "expectedStep": step,
        "expectedRange": [expected[0], expected[-1]] if expected else [],
        "missingCount": len(missing),
        "missingNumbers": missing,
        "missingUnseenFromOriginCount": len(missing_unseen_from_origin),
        "missingUnseenFromOriginNumbers": missing_unseen_from_origin,
        "missingUnseenAtBoardingStationCount": len(missing_unseen_at_boarding_station),
        "missingUnseenAtBoardingStationNumbers": missing_unseen_at_boarding_station,
        "missingUnseenGloballyCount": len(missing_unseen_globally),
        "missingUnseenGloballyNumbers": missing_unseen_globally,
        "coverageDensity": round(density, 3),
        "gapRatio": round(gap_ratio, 3),
        "firstDeparture": min((item["departure"] for item in items if item.get("departure")), default=""),
        "operators": sorted({item["operatorId"] for item in items if item.get("operatorId")}),
        "sources": sorted({item["sourceCollection"] for item in items if item.get("sourceCollection")}),
        "samples": sorted(items, key=lambda item: (item.get("number", 0), item.get("departure", "")))[:12],
    }


def reviewed_gap_pattern(summary: dict[str, Any]) -> dict[str, str] | None:
    review = REVIEWED_GAP_PATTERNS.get(
        (
            str(summary.get("serviceFamily") or ""),
            str(summary.get("origin") or ""),
            str(summary.get("terminal") or ""),
        )
    )
    if not review:
        return None
    return {
        "reviewCategory": review["category"],
        "reviewNote": review["note"],
        "reviewSource": review["source"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-observed", type=int, default=4)
    parser.add_argument("--max-gap-ratio", type=float, default=0.45)
    parser.add_argument("--include-shinkansen", action="store_true")
    args = parser.parse_args()

    payload = load_json(args.input)
    trains = payload.get("train_instances", [])
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    family_counts: Counter[str] = Counter()
    family_numbers: dict[str, set[int]] = defaultdict(set)
    family_origin_numbers: dict[tuple[str, str], set[int]] = defaultdict(set)
    family_station_numbers: dict[tuple[str, str], set[int]] = defaultdict(set)
    skipped_counts: Counter[str] = Counter()

    for train in trains:
        parsed = numbered_family(train)
        if not parsed:
            skipped_counts["not_numbered_named_train"] += 1
            continue
        family, number = parsed
        if not is_limited_express_like(train, family, args.include_shinkansen):
            skipped_counts["not_limited_express_like"] += 1
            continue
        stops = train.get("stop_times") or []
        if len(stops) < 2:
            skipped_counts["short_train"] += 1
            continue
        origin = stop_name(stops[0])
        terminal = stop_name(stops[-1])
        if not origin or not terminal:
            skipped_counts["missing_terminal_name"] += 1
            continue
        family_counts[family] += 1
        family_numbers[family].add(number)
        family_origin_numbers[(family, origin)].add(number)
        seen_station_keys: set[tuple[str, str]] = set()
        for stop in stops:
            station_key = stop_name(stop) or stop_group_id(stop)
            if station_key:
                seen_station_keys.add((family, station_key))
        for station_key in seen_station_keys:
            family_station_numbers[station_key].add(number)
        groups[(family, origin, terminal)].append(
            {
                "number": number,
                "displayName": train.get("display_name") or train.get("service_name_detail") or train.get("route_name") or "",
                "departure": stop_time(stops[0]),
                "trainId": train.get("service_instance_id") or train.get("source_trip_id") or "",
                "operatorId": train.get("operator_id") or "",
                "sourceCollection": train.get("source_collection") or "",
                "sourceUrl": train.get("source_url") or train.get("source_detail_url") or "",
            }
        )

    candidates = []
    high_priority_candidates = []
    reviewed_gap_patterns = []
    reviewed_dense_sequences = []
    for key, items in groups.items():
        numbers = {int(item["number"]) for item in items}
        if len(numbers) < args.min_observed:
            continue
        summary = summarize_group(
            key,
            items,
            family_numbers=family_numbers,
            family_origin_numbers=family_origin_numbers,
            family_station_numbers=family_station_numbers,
        )
        if not summary:
            reviewed_dense_sequences.append(
                {
                    "serviceFamily": key[0],
                    "origin": key[1],
                    "terminal": key[2],
                    "observedCount": len(numbers),
                    "observedNumbers": sorted(numbers),
                }
            )
            continue
        if summary["gapRatio"] <= args.max_gap_ratio:
            review = reviewed_gap_pattern(summary)
            if review:
                reviewed_gap_patterns.append({**summary, **review})
                continue
            candidates.append(summary)
            if summary["missingUnseenAtBoardingStationCount"]:
                high_priority_candidates.append(summary)

    candidates.sort(
        key=lambda item: (
            -item["missingUnseenAtBoardingStationCount"],
            -item["missingUnseenFromOriginCount"],
            -item["missingCount"],
            item["serviceFamily"],
            item["origin"],
            item["terminal"],
        )
    )
    high_priority_candidates.sort(
        key=lambda item: (
            -item["missingUnseenAtBoardingStationCount"],
            -item["missingUnseenFromOriginCount"],
            -item["missingCount"],
            item["serviceFamily"],
            item["origin"],
            item["terminal"],
        )
    )
    reviewed_dense_sequences.sort(key=lambda item: (-item["observedCount"], item["serviceFamily"], item["origin"], item["terminal"]))
    reviewed_gap_patterns.sort(
        key=lambda item: (
            item["reviewCategory"],
            item["serviceFamily"],
            item["origin"],
            item["terminal"],
        )
    )
    result = {
        "schema": "onichase.v4.limited_express_number_gap_audit.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "input": rel(args.input),
        "policy": (
            "Groups numbered named limited-express-like trains by service family, origin, and terminal. "
            "For groups with at least minObserved unique train numbers, it infers step=2 when all numbers share parity, "
            "otherwise step=1, and reports missing numbers within the observed min/max range. "
            "High-priority findings require missing numbers to be absent from that boarding station entirely, "
            "so pass-through trains from a farther origin do not look missing. Findings are review candidates, not automatic errors."
        ),
        "parameters": {
            "minObserved": args.min_observed,
            "maxGapRatio": args.max_gap_ratio,
            "includeShinkansen": args.include_shinkansen,
        },
        "summary": {
            "trainInstanceCount": len(trains),
            "limitedExpressFamilyCount": len(family_counts),
            "numberedLimitedExpressGroupCount": len(groups),
            "gapCandidateCount": len(candidates),
            "highPriorityGapCandidateCount": len(high_priority_candidates),
            "reviewedGapPatternCount": len(reviewed_gap_patterns),
            "reviewedDenseSequenceCount": len(reviewed_dense_sequences),
            "topFamilies": [{"serviceFamily": family, "count": count} for family, count in family_counts.most_common(40)],
            "skippedCounts": dict(skipped_counts),
        },
        "highPriorityGapCandidates": high_priority_candidates,
        "gapCandidates": candidates,
        "reviewedGapPatterns": reviewed_gap_patterns,
        "reviewedDenseSequences": reviewed_dense_sequences[:500],
    }
    write_json(args.output, result)
    print(
        f"Wrote {rel(args.output)}: candidates={len(candidates)} "
        f"high_priority={len(high_priority_candidates)} "
        f"families={len(family_counts)} groups={len(groups)}"
    )
    for item in high_priority_candidates[:20]:
        print(
            f"- {item['serviceFamily']} {item['origin']}->{item['terminal']}: "
            f"missing_at_station={item['missingUnseenAtBoardingStationNumbers']} "
            f"missing_from_origin={item['missingUnseenFromOriginNumbers']} "
            f"missing={item['missingNumbers']} observed={item['observedNumbers']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
