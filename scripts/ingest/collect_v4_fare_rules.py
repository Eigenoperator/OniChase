#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "v4_fare_rules.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_fare_source_cache"

JR_FARE_SOURCES = [
    {
        "key": "jr_hokkaido",
        "operatorIds": ["jr_hokkaido"],
        "url": "https://jr-group.jp/hokkaido-fare/",
        "tables": [
            {"key": "main", "marker": "JR北海道幹線運賃表"},
            {"key": "local", "marker": "JR北海道地方交通線運賃表"},
        ],
    },
    {
        "key": "jr_east",
        "operatorIds": ["jr_east"],
        "url": "https://jr-group.jp/higashinihon-fare/",
        "tables": [
            {"key": "main", "marker": "JR東日本幹線運賃表"},
            {"key": "local", "marker": "JR東日本「地方交通線」運賃表"},
        ],
    },
    {
        "key": "jr_central_west",
        "operatorIds": ["jr_central", "jr_west"],
        "url": "https://jr-group.jp/tokai-fare/",
        "tables": [
            {"key": "main", "marker": "JR東海幹線運賃表"},
            {"key": "local", "marker": "JR東海・JR西日本エリア内の「地方交通線のみを利用する場合」の運賃表"},
        ],
    },
    {
        "key": "jr_shikoku",
        "operatorIds": ["jr_shikoku"],
        "url": "https://jr-group.jp/shikoku-fare/",
        "tables": [
            {"key": "main", "marker": "JR四国の普通運賃表"},
        ],
    },
    {
        "key": "jr_kyushu",
        "operatorIds": ["jr_kyushu"],
        "url": "https://jr-group.jp/kyushu-fare/",
        "tables": [
            {"key": "main", "marker": "JR九州の普通運賃表"},
        ],
    },
]

LIMITED_EXPRESS_SOURCE = {
    "key": "jr_conventional_limited_express",
    "url": "https://jr-group.jp/zairaisen-tokkyu-ryokin/",
    "tables": [
        {"key": "a", "marker": "A特急料金表"},
        {"key": "a_hokkaido", "marker": "JR北海道のA特急料金表"},
        {"key": "b_east_central", "marker": "B特急料金表（JR東日本、JR東海）"},
        {"key": "b_kyushu", "marker": "B特急料金表（JR九州）"},
    ],
}

OFFICIAL_REFERENCE_SOURCES = [
    {
        "key": "jreast_limited_express_ticket",
        "url": "https://www.jreast.co.jp/kippu/1203.html",
        "reason": "JR East official explanation: limited express requires an express ticket, conventional limited express charges are by riding distance.",
    },
]

KITAKYUSHU_MONORAIL_STATION_PAIR_SOURCE = {
    "key": "kitakyushu_monorail_station_pairs",
    "operatorIds": ["北九州高速鉄道"],
    "operatorName": "北九州高速鉄道",
    "url": "https://kitakyushu-monorail.co.jp/fare/ticket.php",
    "routeIds": ["V4_ROUTE_95A9919692CE5D"],
    "notes": [
        "北九州モノレール公式の普通券運賃表から駅間区分を抽出。100円モノレール区間を含む大人普通運賃。",
    ],
}

NEW_SHUTTLE_STATION_PAIR_SOURCE = {
    "key": "new_shuttle_station_pairs",
    "operatorIds": ["埼玉新都市交通"],
    "operatorName": "埼玉新都市交通",
    "url": "https://www.new-shuttle.jp/ticket/pricelist/",
    "routeIds": ["V4_ROUTE_BA8D8FF9F3D5E3"],
    "notes": [
        "ニューシャトル公式の普通片道運賃（きっぷ）駅間表から大人普通運賃を抽出。",
    ],
}

ENODEN_STATION_PAIR_SOURCE = {
    "key": "enoden_station_pairs",
    "operatorIds": ["江ノ島電鉄"],
    "operatorName": "江ノ島電鉄",
    "url": "https://www.enoden.co.jp/train/fare/",
    "routeIds": ["V4_ROUTE_293DEFDC462506"],
    "notes": [
        "江ノ島電鉄公式の普通運賃・所要時間ページ内 fareObj から駅間大人普通運賃を抽出。",
    ],
}

SANRIKU_STATION_PAIR_SOURCE = {
    "key": "sanriku_station_pairs_202603",
    "operatorIds": ["三陸鉄道"],
    "operatorName": "三陸鉄道",
    "url": "https://www.sanrikutetsudou.com/wp-content/uploads/2026/03/20260314futuunchinhyou.pdf",
    "routeIds": [
        "V4_ROUTE_1946C169C0A7D3",
        "V4_ROUTE_CCEF6E6684C4E9",
        "V4_ROUTE_B1E109F61AA54E",
    ],
    "notes": [
        "三陸鉄道公式の2026年3月14日改正普通運賃表から駅間大人普通運賃を抽出。",
    ],
}

KOBE_NEW_TRANSIT_STATION_PAIR_SOURCE = {
    "key": "kobe_new_transit_station_pairs",
    "operatorIds": ["神戸新交通"],
    "operatorName": "神戸新交通",
    "url": "https://www.knt-liner.co.jp/ticket/fee/",
    "routeIds": ["V4_ROUTE_7525EA6275E923", "V4_ROUTE_1F959938CAAAC0"],
    "notes": [
        "神戸新交通公式の普通旅客運賃表からポートライナー・六甲ライナーの駅間大人普通運賃を抽出。",
    ],
}

WAKAYAMA_DENTETSU_STATION_PAIR_SOURCE = {
    "key": "wakayama_dentetsu_station_pairs_202605",
    "operatorIds": ["和歌山電鐵"],
    "operatorName": "和歌山電鐵",
    "url": "https://wakayama-dentetsu.co.jp/fare/",
    "routeIds": ["V4_ROUTE_F82B58357C2811"],
    "notes": [
        "和歌山電鐵公式の普通運賃ページに掲載された乗車駅別普通運賃表から大人普通運賃を抽出。",
    ],
}

SENDAI_AIRPORT_TRANSIT_STATION_PAIR_SOURCE = {
    "key": "sendai_airport_transit_station_pairs_202603",
    "operatorIds": ["仙台空港鉄道"],
    "operatorName": "仙台空港鉄道",
    "routeIds": ["V4_ROUTE_660D6C88CEEFD5"],
    "pages": [
        ("仙台", "https://www.senat.co.jp/fare/sendai/"),
        ("長町", "https://www.senat.co.jp/fare/nagamachi/"),
        ("太子堂", "https://www.senat.co.jp/fare/taishidou/"),
        ("南仙台", "https://www.senat.co.jp/fare/minamisen/"),
        ("名取", "https://www.senat.co.jp/fare/natori/"),
        ("杜せきのした", "https://www.senat.co.jp/fare/moriseki/"),
        ("美田園", "https://www.senat.co.jp/fare/mitazono/"),
        ("仙台空港", "https://www.senat.co.jp/fare/sendaiair/"),
    ],
    "notes": [
        "仙台空港鉄道公式の各駅運賃ページに掲載されたきっぷ大人運賃を駅間表として抽出。",
    ],
}

AONAMI_LINE_STATION_PAIR_SOURCE = {
    "key": "aonami_line_station_pairs_2026",
    "operatorIds": ["名古屋臨海高速鉄道"],
    "operatorName": "名古屋臨海高速鉄道",
    "routeIds": ["V4_ROUTE_8347D8D79CF2BA"],
    "pages": [
        ("名古屋", "https://www.aonamiline.co.jp/train/an01-nagoya/an01-fare"),
        ("ささしまライブ", "https://www.aonamiline.co.jp/train/an02-sasashima-raibu/an02-fare"),
        ("小本", "https://www.aonamiline.co.jp/train/an03-komoto/an03-fare"),
        ("荒子", "https://www.aonamiline.co.jp/train/an04-arako/an04-fare"),
        ("南荒子", "https://www.aonamiline.co.jp/train/an05-minami-arako/an05-fare"),
        ("中島", "https://www.aonamiline.co.jp/train/an06-nakajima/an06-fare"),
        ("港北", "https://www.aonamiline.co.jp/train/an07-kohoku/an07-fare"),
        ("荒子川公園", "https://www.aonamiline.co.jp/train/an08-arakogawa-koen/an08-fare"),
        ("稲永", "https://www.aonamiline.co.jp/train/an09-inaei/an09-fare"),
        ("野跡", "https://www.aonamiline.co.jp/train/an10-noseki/an10-fare"),
        ("金城ふ頭", "https://www.aonamiline.co.jp/train/an11-kinjo-futo/an11-fare"),
    ],
    "notes": [
        "あおなみ線公式の各駅運賃表に掲載された大人普通運賃を駅間表として抽出。",
    ],
}

TAMA_MONORAIL_STATION_PAIR_SOURCE = {
    "key": "tama_monorail_station_pairs_2026",
    "operatorIds": ["tama_monorail"],
    "operatorName": "多摩都市モノレール",
    "routeIds": ["V4_ROUTE_E05060FC18A845"],
    "pages": [
        ("上北台", "https://www.tama-monorail.co.jp/monorail/station/kamikitadai/fare.html"),
        ("桜街道", "https://www.tama-monorail.co.jp/monorail/station/sakurakaido/fare.html"),
        ("玉川上水", "https://www.tama-monorail.co.jp/monorail/station/tamagawajosui/fare.html"),
        ("砂川七番", "https://www.tama-monorail.co.jp/monorail/station/sunagawa-nanaban/fare.html"),
        ("泉体育館", "https://www.tama-monorail.co.jp/monorail/station/izumi-taiikukan/fare.html"),
        ("立飛", "https://www.tama-monorail.co.jp/monorail/station/tachihi/fare.html"),
        ("高松", "https://www.tama-monorail.co.jp/monorail/station/takamatsu/fare.html"),
        ("立川北", "https://www.tama-monorail.co.jp/monorail/station/tachikawa-kita/fare.html"),
        ("立川南", "https://www.tama-monorail.co.jp/monorail/station/tachikawa-minami/fare.html"),
        ("柴崎体育館", "https://www.tama-monorail.co.jp/monorail/station/shibasaki-taiikukan/fare.html"),
        ("甲州街道", "https://www.tama-monorail.co.jp/monorail/station/koshukaido/fare.html"),
        ("万願寺", "https://www.tama-monorail.co.jp/monorail/station/manganji/fare.html"),
        ("高幡不動", "https://www.tama-monorail.co.jp/monorail/station/takahatafudo/fare.html"),
        ("程久保", "https://www.tama-monorail.co.jp/monorail/station/hodokubo/fare.html"),
        ("多摩動物公園", "https://www.tama-monorail.co.jp/monorail/station/tama-dobutsukoen/fare.html"),
        ("中央大学・明星大学", "https://www.tama-monorail.co.jp/monorail/station/chuo-daigaku-meisei-daigaku/fare.html"),
        ("大塚・帝京大学", "https://www.tama-monorail.co.jp/monorail/station/otsuka-teikyo-daigaku/fare.html"),
        ("松が谷", "https://www.tama-monorail.co.jp/monorail/station/matsugaya/fare.html"),
        ("多摩センター", "https://www.tama-monorail.co.jp/monorail/station/tama-center/fare.html"),
    ],
    "notes": [
        "多摩モノレール公式の各駅運賃・所要時間ページから、きっぷ大人普通運賃を駅間表として抽出。",
    ],
}

LINIMO_STATION_PAIR_SOURCE = {
    "key": "linimo_station_pairs_202604",
    "operatorIds": ["愛知高速交通"],
    "operatorName": "愛知高速交通",
    "routeIds": ["V4_ROUTE_B9AC66005C8F85"],
    "pages": [
        ("藤が丘", "https://www.linimo.jp/station/2018030611485318.html"),
        ("はなみずき通", "https://www.linimo.jp/station/2018030614050137.html"),
        ("杁ヶ池公園", "https://www.linimo.jp/station/2018030614142550.html"),
        ("長久手古戦場", "https://www.linimo.jp/station/2018030614204396.html"),
        ("芸大通", "https://www.linimo.jp/station/2018030614265795.html"),
        ("公園西", "https://www.linimo.jp/station/2018030614330679.html"),
        ("愛・地球博記念公園", "https://www.linimo.jp/station/2018020517154892.html"),
        ("陶磁資料館南", "https://www.linimo.jp/station/2018030614392599.html"),
        ("八草", "https://www.linimo.jp/station/2018030614442117.html"),
    ],
    "notes": [
        "愛知高速交通リニモ公式の各駅普通乗車券ページから大人普通運賃を駅間表として抽出。",
    ],
}

UEDA_DENTETSU_STATION_PAIR_SOURCE = {
    "key": "ueda_dentetsu_station_pairs_201910",
    "operatorIds": ["上田電鉄"],
    "operatorName": "上田電鉄",
    "url": "https://www.uedadentetsu.com/fare/index.html",
    "routeIds": ["V4_ROUTE_A9966DAEF9105D"],
    "stationOrder": [
        "上田", "城下", "三好町", "赤坂上", "上田原", "寺下", "神畑", "大学前",
        "下之郷", "中塩田", "塩田町", "中野", "舞田", "八木沢", "別所温泉",
    ],
    "notes": [
        "上田電鉄公式の別所線普通券運賃表から大人普通運賃の三角表を抽出。",
    ],
}

CHIKUTETSU_STATION_PAIR_SOURCE = {
    "key": "chikutetsu_station_pairs_202409",
    "operatorIds": ["筑豊電気鉄道"],
    "operatorName": "筑豊電気鉄道",
    "url": "https://www.chikutetsu.co.jp/sta_pdf/unchin.pdf",
    "routeIds": ["V4_ROUTE_517E3EEFBD0DBF"],
    "stationOrder": [
        "筑豊直方", "感田", "遠賀野", "木屋瀬", "新木屋瀬", "楠橋",
        "筑豊香月", "希望が丘高校前", "筑豊中間", "東中間", "通谷",
        "西山", "三ヶ森", "永犬丸", "今池", "森下", "穴生",
        "萩原", "熊西", "黒崎駅前",
    ],
    "notes": [
        "筑豊電気鉄道公式の運賃・キロ程表PDFから現金（普通券）大人運賃の三角表を抽出。",
    ],
}

FUKUSHIMA_KOTSU_IIZAKA_STATION_PAIR_SOURCE = {
    "key": "fukushima_kotsu_iizaka_station_pairs_202505",
    "operatorIds": ["福島交通"],
    "operatorName": "福島交通",
    "url": "https://ii-den.jp/files/newsrelease/files/0129_file02.pdf",
    "routeIds": ["V4_ROUTE_63F2F02E85FE15"],
    "stationOrder": [
        "福島", "曽根田", "美術館図書館前", "岩代清水", "泉", "上松川",
        "笹谷", "桜水", "平野", "医王寺前", "花水坂", "飯坂温泉",
    ],
    "notes": [
        "福島交通公式の2025年5月17日改定飯坂線普通旅客運賃表PDFから大人普通運賃の三角表を抽出。",
    ],
}

AICHI_LOOP_STATION_PAIR_SOURCE = {
    "key": "aichi_loop_station_pairs_202503",
    "operatorIds": ["愛知環状鉄道"],
    "operatorName": "愛知環状鉄道",
    "url": "https://www.aikanrailway.co.jp/pdf/price_normal.pdf",
    "routeIds": ["V4_ROUTE_C291999D273BB1"],
    "stationOrder": [
        "高蔵寺", "中水野", "瀬戸市", "瀬戸口", "山口", "八草", "篠原",
        "保見", "貝津", "四郷", "愛環梅坪", "新豊田", "新上挙母",
        "三河豊田", "末野原", "永覚", "三河上郷", "北野桝塚", "大門",
        "北岡崎", "中岡崎", "六名", "岡崎",
    ],
    "notes": [
        "愛知環状鉄道公式の2025年3月15日改定普通券・定期券運賃表PDFから普通券大人運賃の三角表を抽出。",
    ],
}

SHIMABARA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "shimabara_railway_station_pairs_202604",
    "operatorIds": ["島原鉄道"],
    "operatorName": "島原鉄道",
    "url": "https://www.shimatetsu.co.jp/upload/save/content/button/41ba50f3e17660e5f1044b47df1ed4e1.pdf",
    "routeIds": ["V4_ROUTE_4CF71AC3B1F0DC"],
    "stationOrder": [
        "諫早", "本諫早", "幸", "小野", "干拓の里", "森山", "釜ノ鼻",
        "諫早東高校", "愛野", "阿母崎", "吾妻", "古部", "大正",
        "西郷", "神代", "多比良", "有明湯江", "大三東", "松尾",
        "三会", "島原", "霊丘公園", "島原船津", "島原港",
    ],
    "notes": [
        "島原鉄道公式の2026年4月1日改正普通旅客運賃表PDFから駅間大人普通運賃の三角表を抽出。",
    ],
}

IBARA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "ibara_railway_station_pairs_202510",
    "operatorIds": ["井原鉄道"],
    "operatorName": "井原鉄道",
    "url": "https://www.ibara-railway.co.jp/wp-content/uploads/2025/09/f8dca081c7d888a86d0fd595a8752833.pdf",
    "routeIds": ["V4_ROUTE_1A350AB2DFD5B6"],
    "stationOrder": [
        "総社", "清音", "川辺宿", "吉備真備", "備中呉妹", "三谷", "矢掛",
        "小田", "早雲の里荏原", "井原", "いずえ", "子守唄の里高屋",
        "御領", "湯野", "神辺",
    ],
    "notes": [
        "井原鉄道公式の2025年10月1日改定普通旅客運賃表PDFから大人普通運賃の三角表を抽出。総社-清音は公式注記の特定運賃190円を適用。",
    ],
}

KASHIMA_RINKAI_STATION_PAIR_SOURCE = {
    "key": "kashima_rinkai_station_pairs_202603",
    "operatorIds": ["鹿島臨海鉄道"],
    "operatorName": "鹿島臨海鉄道",
    "url": "https://www.rintetsu.co.jp/wp-content/uploads/2026/03/5d068f3d57fdee6c10b5a8936a456fdc.pdf",
    "routeIds": ["V4_ROUTE_06B853D81B2B75"],
    "stationOrder": [
        "水戸", "東水戸", "常澄", "大洗", "涸沼", "鹿島旭", "徳宿",
        "新鉾田", "北浦湖畔", "大洋", "鹿島灘", "鹿島大野",
        "長者ヶ浜潮騒はまなす公園前", "荒野台", "鹿島サッカースタジアム",
        "鹿島神宮",
    ],
    "notes": [
        "鹿島臨海鉄道公式の2026年3月14日改定普通旅客運賃表PDFから大洗鹿島線関連の大人普通運賃を抽出。荒野台-鹿島サッカースタジアムは線内普通運賃230円を採用し、JR鹿島神宮相互利用時の特殊割引運賃は別条件のため未適用。",
    ],
}

YAMAGATA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "yamagata_railway_station_pairs",
    "operatorIds": ["山形鉄道"],
    "operatorName": "山形鉄道",
    "url": "https://flower-liner.jp/fare/",
    "routeIds": ["V4_ROUTE_4D7811873081BC"],
    "notes": [
        "山形鉄道公式サイトのフラワー長井線普通旅客運賃表から大人普通運賃の駅間表を抽出。",
    ],
}

MOKA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "moka_railway_station_pairs",
    "operatorIds": ["真岡鐵道"],
    "operatorName": "真岡鐵道",
    "url": "https://www.moka-railway.co.jp/fare/",
    "routeIds": ["V4_ROUTE_96548170FFBBE9"],
    "notes": [
        "真岡鐵道公式サイトの2019年10月1日改定普通運賃表から大人普通運賃の駅間表を抽出。SL乗車時のSL整理券は別料金のため未適用。",
    ],
}

# Real adult ordinary fare tables from official operator fare pages/PDFs.
# Values use the ticket / 10-yen unit fare where operators publish both IC and ticket fares,
# because gameplay fares are displayed as a simple yen total and should avoid 1-yen IC rounding details.
MANUAL_OPERATOR_FARE_TABLES = [
    {
        "key": "kintetsu",
        "operatorIds": ["近畿日本鉄道"],
        "operatorName": "近畿日本鉄道",
        "url": "https://www.kintetsu.co.jp/gyoumu/kippu/pdf/kirotei_20260314.pdf",
        "notes": [
            "普通旅客運賃・鉄軌道線の大人普通運賃。吉野線/湯の山線/志摩線、鳥羽線、けいはんな線などの加算運賃は未適用。",
        ],
        "rows": [
            (1, 3, 180), (4, 6, 240), (7, 10, 300), (11, 14, 360), (15, 18, 430),
            (19, 22, 490), (23, 26, 530), (27, 30, 590), (31, 35, 680), (36, 40, 760),
            (41, 45, 830), (46, 50, 910), (51, 55, 1000), (56, 60, 1070), (61, 65, 1140),
            (66, 70, 1210), (71, 75, 1290), (76, 80, 1370), (81, 85, 1450), (86, 90, 1530),
            (91, 95, 1600), (96, 100, 1670), (101, 110, 1740), (111, 120, 1880), (121, 130, 2040),
            (131, 140, 2170), (141, 150, 2310), (151, 160, 2430), (161, 170, 2560),
            (171, 180, 2710), (181, 190, 2860), (191, 200, 3000), (201, 210, 3130),
            (211, 220, 3280), (221, 230, 3410), (231, 240, 3560), (241, 250, 3690),
        ],
    },
    {
        "key": "tobu",
        "operatorIds": ["tobu"],
        "operatorName": "東武鉄道",
        "url": "https://www.tobu.co.jp/pdf/ticket/unchinTable.pdf?2023=",
        "notes": ["大人普通運賃。運賃計算キロによる距離分段。"],
        "rows": [
            (1, 4, 160), (5, 7, 180), (8, 10, 210), (11, 15, 270), (16, 20, 330),
            (21, 25, 380), (26, 30, 430), (31, 35, 490), (36, 40, 540), (41, 45, 610),
            (46, 50, 670), (51, 60, 750), (61, 70, 830), (71, 80, 920), (81, 90, 1000),
            (91, 100, 1090), (101, 120, 1230), (121, 140, 1400), (141, 178, 1590),
        ],
    },
    {
        "key": "seibu",
        "operatorIds": ["seibu"],
        "operatorName": "西武鉄道",
        "url": "https://www.seiburailway.jp/file.jsp?file%2F202603_fare_bykm.pdf=",
        "notes": ["2025年7月改定後の大人普通旅客運賃・きっぷ10円単位。"],
        "rows": [
            (1, 4, 170), (5, 8, 210), (9, 12, 250), (13, 16, 290), (17, 20, 330),
            (21, 24, 370), (25, 28, 410), (29, 32, 450), (33, 36, 490), (37, 40, 530),
            (41, 44, 560), (45, 48, 600), (49, 52, 630), (53, 56, 660), (57, 60, 690),
            (61, 64, 710), (65, 68, 740), (69, 72, 760), (73, 76, 790), (77, 81, 800),
        ],
    },
    {
        "key": "hankyu",
        "operatorIds": ["阪急電鉄"],
        "operatorName": "阪急電鉄",
        "url": "https://www.hankyu.co.jp/files/upload/topics/230117Bar/230117_ft.pdf",
        "notes": ["2023年4月1日以降の鉄道駅バリアフリー料金加算後の改定普通運賃（大人）。"],
        "rows": [
            (1, 4, 170), (5, 9, 200), (10, 14, 240), (15, 19, 280),
            (20, 26, 290), (27, 33, 330), (34, 42, 390), (43, 51, 410),
            (52, 60, 480), (61, 70, 540), (71, 76, 640),
        ],
    },
    {
        "key": "sanyo_railway_202501",
        "operatorIds": ["山陽電気鉄道"],
        "operatorName": "山陽電気鉄道",
        "url": "https://www.sanyo-railway.co.jp/media/1724821276.pdf",
        "notes": ["2025年1月19日改定の普通旅客運賃（鉄道駅バリアフリー料金を含む）。"],
        "routeIds": ["V4_ROUTE_A161B9B7A92889", "V4_ROUTE_74DDF18E66DBF2"],
        "rows": [
            (1, 2, 170), (3, 4, 200), (5, 7, 250), (8, 10, 320),
            (11, 13, 390), (14, 17, 470), (18, 21, 540), (22, 25, 600),
            (26, 29, 650), (30, 34, 710), (35, 39, 740), (40, 44, 770),
            (45, 49, 810), (50, 54, 840), (55, 60, 860),
        ],
    },
    {
        "key": "keisei_main_202603",
        "operatorIds": ["keisei"],
        "operatorName": "京成電鉄",
        "url": "https://new-www.keisei.co.jp/keisei/tetudou/goriyo/pdf/keisei_260314.pdf",
        "notes": [
            "2026年3月14日現在の旅客営業規則第77条第1項の大人片道普通旅客運賃。空港加算運賃・成田空港線併算・千原線内運賃は別体系。",
        ],
        "routeIds": [
            "V4_ROUTE_AF3DADBA36B0AE",
            "V4_ROUTE_4DDE1DDBC9F48A",
            "V4_ROUTE_E67CFC3198A6A5",
            "V4_ROUTE_E8462BA3669C4E",
            "V4_ROUTE_D46B19B1C06952",
        ],
        "rows": [
            (1, 3, 140), (4, 5, 160), (6, 10, 190), (11, 15, 270),
            (16, 20, 330), (21, 25, 380), (26, 30, 440), (31, 35, 500),
            (36, 40, 550), (41, 45, 610), (46, 50, 680), (51, 55, 740),
            (56, 60, 790), (61, 65, 850), (66, 70, 910),
        ],
    },
    {
        "key": "keisei_chihara_201910",
        "operatorIds": ["keisei"],
        "operatorName": "京成電鉄",
        "url": "https://new-www.keisei.co.jp/keisei/tetudou/goriyo/pdf/keisei_260314.pdf",
        "notes": ["旅客営業規則別表第2号の4に掲載された千原線内適用のキロ別普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_3492E341CE56F0"],
        "rows": [
            (1, 3, 190), (4, 5, 260), (6, 6, 280), (7, 7, 300),
            (8, 8, 320), (9, 9, 330), (10, 10, 350), (11, 11, 370),
        ],
    },
    {
        "key": "tokyu",
        "operatorIds": ["tokyu"],
        "operatorName": "東急電鉄",
        "url": "https://www.tokyu.co.jp/railway/ticket/fares/?vm=r",
        "notes": [
            "片道普通旅客運賃表の大人きっぷ10円単位。世田谷線/こどもの国線は別体系のためこの表では覆わない。",
            "東急新横浜線の加算運賃は未適用。",
        ],
        "routeIds": [
            "V4_ROUTE_56F81486403338",
            "V4_ROUTE_DA71FF0BA2DDB7",
            "V4_ROUTE_C6F1D11C9AEA86",
            "V4_ROUTE_46D0A707F27623",
            "V4_ROUTE_A738E69EA02361",
            "V4_ROUTE_AC3B165463EF1E",
            "V4_ROUTE_C91FD9313F0927",
        ],
        "rows": [
            (1, 3, 140), (4, 7, 180), (8, 11, 230), (12, 15, 250), (16, 20, 290),
            (21, 25, 310), (26, 30, 350), (31, 35, 390), (36, 40, 430),
        ],
    },
    {
        "key": "tokyu_setagaya_flat",
        "operatorIds": ["tokyu"],
        "operatorName": "東急電鉄",
        "url": "https://www.tokyu.co.jp/railway/sg/howto/",
        "notes": ["世田谷線の現金/IC/クレジット共通の均一普通運賃。"],
        "routeIds": ["V4_ROUTE_E15201069F9365"],
        "rows": [(1, None, 160)],
    },
    {
        "key": "tokyu_kodomonokuni_flat",
        "operatorIds": ["tokyu"],
        "operatorName": "東急電鉄",
        "url": "https://www.tokyu.co.jp/railway/ticket/fares/?vm=r",
        "notes": ["東急公式のこどもの国線普通旅客運賃表（均一制）。きっぷ大人普通運賃。"],
        "routeIds": ["V4_ROUTE_446823A8E04390"],
        "rows": [(1, None, 160)],
    },
    {
        "key": "tokyo_metro",
        "operatorIds": ["tokyo_metro"],
        "operatorName": "東京地下鉄",
        "url": "https://www.tokyometro.jp/ticket/types/regular/index.html",
        "notes": ["東京メトロ普通旅客運賃・きっぷ10円単位。"],
        "rows": [(1, 6, 180), (7, 11, 210), (12, 19, 260), (20, 27, 300), (28, 40, 330)],
    },
    {
        "key": "toei_subway",
        "operatorIds": ["toei"],
        "operatorName": "東京都交通局",
        "url": "https://www.kotsu.metro.tokyo.jp/subway/fare/regular.html",
        "notes": ["都営地下鉄普通旅客運賃・きっぷ10円単位。都電荒川線と日暮里・舎人ライナーは別体系のため覆わない。"],
        "routeIds": [
            "V4_ROUTE_69910AA21F287E",
            "V4_ROUTE_AD0AF842F60ABA",
            "V4_ROUTE_4C214F5229C9F9",
            "V4_ROUTE_5C2771F026AC80",
        ],
        "rows": [(1, 4, 180), (5, 9, 220), (10, 15, 280), (16, 21, 330), (22, 27, 380), (28, 46, 430)],
    },
    {
        "key": "toei_toden_flat",
        "operatorIds": ["toei"],
        "operatorName": "東京都交通局",
        "url": "https://www.kotsu.metro.tokyo.jp/toden/fare/",
        "notes": ["東京さくらトラム（都電荒川線）の現金大人均一普通運賃。"],
        "routeIds": ["V4_ROUTE_03497F30E9FBFB"],
        "rows": [(1, None, 170)],
    },
    {
        "key": "toei_nippori_toneri_liner",
        "operatorIds": ["toei"],
        "operatorName": "東京都交通局",
        "url": "https://www.kotsu.metro.tokyo.jp/nippori_toneri/fare/regular.html",
        "notes": ["日暮里・舎人ライナーの10円単位普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_1FB5150DC711CC"],
        "rows": [(1, 2, 170), (3, 4, 240), (5, 7, 290), (8, 10, 340)],
    },
    {
        "key": "osaka_metro",
        "operatorIds": ["大阪市高速電気軌道"],
        "operatorName": "Osaka Metro",
        "url": "https://subway.osakametro.co.jp/guide/fare/fare/price.php",
        "notes": ["Osaka Metro普通運賃の区数制。距離上限で近似せず、公式区数の距離境界を使用。"],
        "rows": [(1, 3, 190), (4, 7, 240), (8, 13, 290), (14, 19, 340), (20, 100, 390)],
    },
    {
        "key": "sendai_subway_201910",
        "operatorIds": ["仙台市"],
        "operatorName": "仙台市交通局",
        "url": "https://www.kotsu.city.sendai.jp/assets/img/fare/unchin/unchin.pdf",
        "notes": [
            "令和6年度資料の地下鉄普通乗車券・対キロ区間制。仙台駅中心の3駅均一運賃は station-pair 特例として未適用。",
        ],
        "routeIds": ["V4_ROUTE_D3D48A3812F260", "V4_ROUTE_8524C7C2A8A068"],
        "rows": [(1, 3, 210), (4, 6, 250), (7, 9, 310), (10, 12, 340), (13, None, 370)],
    },
    {
        "key": "osaka_monorail_201910",
        "operatorIds": ["大阪モノレル"],
        "operatorName": "大阪モノレール",
        "url": "https://www.osaka-monorail.co.jp/common/pdf/fares_20191001.pdf",
        "notes": ["2019年10月1日改正の普通運賃・キロ程表。運賃計算キロは1km未満端数切り上げ。"],
        "routeIds": ["V4_ROUTE_A0C96269989D55", "V4_ROUTE_7A61104BF8E409"],
        "rows": [
            (1, 2, 200), (3, 4, 250), (5, 6, 290), (7, 8, 340),
            (9, 10, 380), (11, 12, 410), (13, 14, 440), (15, 16, 470),
            (17, 22, 500),
        ],
    },
    {
        "key": "tokyo_monorail_202403",
        "operatorIds": ["tokyo_monorail"],
        "operatorName": "東京モノレール",
        "url": "https://www.mlit.go.jp/common/001613622.pdf",
        "notes": ["2024年3月実施の改定上限運賃・普通旅客運賃（大人）10円単位。"],
        "routeIds": ["V4_ROUTE_5EE0E74B2B815C"],
        "rows": [
            (1, 1, 180), (2, 5, 230), (6, 8, 320),
            (9, 11, 390), (12, 14, 460), (15, 18, 520),
        ],
    },
    {
        "key": "okinawa_yui_rail_202502",
        "operatorIds": ["沖縄都市モノレル"],
        "operatorName": "沖縄都市モノレール",
        "url": "https://www.yui-rail.co.jp/ticketinfo-ticket/ticketinfo/",
        "notes": ["2025年2月1日改定後のゆいレール大人普通旅客運賃。対キロ区間制。"],
        "routeIds": ["V4_ROUTE_15C6803E6E69FF"],
        "rows": [(1, 3, 250), (4, 6, 290), (7, 9, 320), (10, 13, 360), (14, 17, 390)],
    },
    {
        "key": "utsunomiya_lightline_202308",
        "operatorIds": ["宇都宮ライトレル"],
        "operatorName": "宇都宮ライトレール",
        "url": "https://www.miyarail.co.jp/rail-fare",
        "notes": ["2023年8月26日開業時の対キロ区間制普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_6608A6D5448558"],
        "rows": [(1, 3, 150), (4, 5, 200), (6, 7, 250), (8, 10, 300), (11, 13, 350), (14, 15, 400)],
    },
    {
        "key": "rinkai_line_201910",
        "operatorIds": ["rinkai"],
        "operatorName": "東京臨海高速鉄道",
        "url": "https://www.twr.co.jp/Portals/0/resources/info/2019/20190906_fare%20revision.pdf",
        "notes": ["2019年10月1日改定のりんかい線普通旅客運賃。公式の運賃区数対応表を距離区分に写したもの。"],
        "routeIds": ["V4_ROUTE_07B6D9691E858A"],
        "rows": [(1, 3, 210), (4, 6, 280), (7, 9, 340), (10, 13, 400)],
    },
    {
        "key": "keio",
        "operatorIds": ["keio"],
        "operatorName": "京王電鉄",
        "url": "https://www.keio.co.jp/train/ticket/fare_chart/fare_chart_km.html",
        "notes": ["2023年10月1日改定のキロ別旅客運賃表・大人普通運賃・きっぷ10円単位。"],
        "rows": [(1, 4, 140), (5, 6, 160), (7, 9, 190), (10, 12, 210), (13, 15, 230),
                 (16, 19, 280), (20, 24, 320), (25, 30, 360), (31, 37, 390),
                 (38, 44, 410), (45, 52, 430)],
    },
    {
        "key": "keikyu_202310",
        "operatorIds": ["keikyu"],
        "operatorName": "京浜急行電鉄",
        "url": "https://www.keikyu.co.jp/cp/unchinkaitei/pdf/futsuu_unchin.pdf",
        "notes": ["2023年10月1日改定の普通旅客運賃（大人）・10円単位きっぷ運賃。"],
        "rows": [
            (1, 3, 150), (4, 6, 180), (7, 10, 230), (11, 15, 280),
            (16, 20, 320), (21, 25, 350), (26, 30, 410), (31, 35, 460),
            (36, 40, 510), (41, 45, 570), (46, 50, 620), (51, 55, 670),
            (56, 60, 710), (61, 67, 740),
        ],
    },
    {
        "key": "shintetsu_202501",
        "operatorIds": ["神戸電鉄"],
        "operatorName": "神戸電鉄",
        "url": "https://www.shintetsu.co.jp/railway/info/01_ryoki.pdf",
        "notes": ["2025年1月19日改定の旅客営業規則別表第3号・大人普通旅客運賃。"],
        "rows": [
            (1, 2, 210), (3, 4, 270), (5, 6, 340), (7, 8, 390),
            (9, 10, 440), (11, 12, 480), (13, 14, 520), (15, 17, 560),
            (18, 20, 600), (21, 23, 640), (24, 26, 670), (27, 29, 700),
            (30, 32, 720), (33, 36, 750), (37, 40, 780), (41, 44, 810),
            (45, 49, 830), (50, 54, 850), (55, 58, 880),
        ],
    },
    {
        "key": "hanshin_main_202603",
        "operatorIds": ["阪神電気鉄道"],
        "operatorName": "阪神電気鉄道",
        "url": "https://www.hanshin.co.jp/ticket/yakkan/pdf/hanshin-passenger.pdf",
        "notes": [
            "2026年3月14日現在の阪神線旅客営業規則別表2号・第58条の大人普通旅客運賃。阪神なんば線の大阪難波-西九条加算運賃は別体系のためこの表では覆わない。",
        ],
        "routeIds": ["V4_ROUTE_590D4A0AC01454", "V4_ROUTE_1D3A859BEF7F27"],
        "rows": [
            (1, 4, 160), (5, 8, 200), (9, 13, 250), (14, 18, 280),
            (19, 24, 300), (25, 30, 320), (31, 34, 330),
        ],
    },
    {
        "key": "chiba_urban_monorail_201910",
        "operatorIds": ["千葉都市モノレル"],
        "operatorName": "千葉都市モノレール",
        "url": "https://chiba-monorail.co.jp/index.php/ryoukin/",
        "notes": ["2019年10月1日改定の千葉都市モノレール公式普通旅客運賃表・きっぷ運賃。"],
        "routeIds": ["V4_ROUTE_09504CFAFABF58", "V4_ROUTE_9CAFC1BEFCAEB2"],
        "rows": [
            (1, 2, 200), (3, 3, 220), (4, 6, 290), (7, 7, 340),
            (8, 9, 390), (10, 11, 430), (12, 13, 480), (14, 14, 520),
        ],
    },
    {
        "key": "ryutetsu_202404",
        "operatorIds": ["流鉄"],
        "operatorName": "流鉄",
        "url": "https://www.ryutetsu.jp/info/wp-content/uploads/2024/02/2024%E5%B9%B44%E6%9C%881%E6%97%A5%E6%94%B9%E6%AD%A3%E9%81%8B%E8%B3%83%E8%A1%A8.pdf",
        "notes": ["2024年4月1日改正の流鉄流山線キロ別普通旅客運賃表。"],
        "routeIds": ["V4_ROUTE_BC12B87F3168A6"],
        "rows": [(1, 2, 140), (3, 3, 150), (4, 4, 190), (5, 5, 200), (6, 6, 220)],
    },
    {
        "key": "sagano_scenic_railway_flat_2026",
        "operatorIds": ["嵯峨野観光鉄道"],
        "operatorName": "嵯峨野観光鉄道",
        "url": "https://www.sagano-kanko.co.jp/ticket/",
        "notes": ["嵯峨野観光鉄道公式の片道普通運賃。乗車区間にかかわらず均一。"],
        "routeIds": ["V4_ROUTE_0BEECC95790117"],
        "rows": [(1, None, 880)],
    },
    {
        "key": "rokko_cable_flat_202504",
        "operatorIds": ["神戸六甲鉄道"],
        "operatorName": "神戸六甲鉄道",
        "url": "https://www.rokkocable.com/information/",
        "notes": ["神戸六甲鉄道公式の六甲ケーブル片道大人普通運賃。"],
        "routeIds": ["V4_ROUTE_61A085D8958B26"],
        "rows": [(1, None, 800)],
    },
    {
        "key": "keifuku_eizan_cable_flat_2026",
        "operatorIds": ["京福電気鉄道"],
        "operatorName": "京福電気鉄道",
        "url": "https://www.keifuku.co.jp/cms/eizan_ticket/",
        "notes": ["京福電気鉄道公式の叡山ケーブル（ケーブル八瀬-ケーブル比叡）片道大人普通運賃。"],
        "routeIds": ["V4_ROUTE_93565FD53B65A0"],
        "rows": [(1, None, 600)],
    },
    {
        "key": "sarakura_cable_flat_202004",
        "operatorIds": ["皿倉登山鉄道"],
        "operatorName": "皿倉登山鉄道",
        "url": "https://www.sarakurayama-cablecar.co.jp/wp-content/uploads/2020/06/sarakurayamadantaiwaribiki2020.pdf",
        "notes": ["皿倉登山鉄道公式の皿倉山ケーブルカー普通運賃表。ケーブルカーのみ乗車の場合の大人片道普通運賃。"],
        "routeIds": ["V4_ROUTE_31939D0CF210B8"],
        "rows": [(1, None, 430)],
    },
    {
        "key": "maya_cable_flat_2026",
        "operatorIds": ["こうべ未来都市機構"],
        "operatorName": "こうべ未来都市機構",
        "url": "https://koberope.jp/maya/price",
        "notes": ["こうべ未来都市機構公式の摩耶ケーブル線片道大人普通運賃。"],
        "routeIds": ["V4_ROUTE_4FDE9609029721"],
        "rows": [(1, None, 450)],
    },
    {
        "key": "seikan_tunnel_museum_incline_flat_2026",
        "operatorIds": ["一般財団法人青函トンネル記念館"],
        "operatorName": "一般財団法人青函トンネル記念館",
        "url": "https://seikan-tunnel-museum.jp/info.html",
        "notes": ["青函トンネル記念館公式の体験坑道乗車券。大人片道乗車相当として扱う。"],
        "routeIds": ["V4_ROUTE_883FC855768AA4"],
        "rows": [(1, None, 1200)],
    },
    {
        "key": "astram_line_202510",
        "operatorIds": ["広島高速交通"],
        "operatorName": "広島高速交通",
        "url": "https://www.astramline.co.jp/Portals/0/pdf/ride-guidance/%E2%97%8E20251001_sikakuhyo.pdf",
        "notes": ["2025年10月1日改定のアストラムライン普通旅客運賃表。大人普通運賃の距離帯。"],
        "routeIds": ["V4_ROUTE_1781D08B1AE1F8"],
        "rows": [(1, 2, 220), (3, 4, 260), (5, 6, 300), (7, 9, 350),
                 (10, 12, 400), (13, 15, 430), (16, 18, 460), (19, 19, 490)],
    },
    {
        "key": "sotetsu",
        "operatorIds": ["sotetsu"],
        "operatorName": "相模鉄道",
        "url": "https://www.sotetsu.co.jp/media/2019/trans/train/search/pdf/kiro_fares.pdf",
        "notes": ["キロ別旅客運賃表・大人普通運賃・きっぷ10円単位。いずみ野線加算運賃は未適用。"],
        "rows": [(1, 3, 150), (4, 7, 180), (8, 11, 200), (12, 15, 230),
                 (16, 19, 260), (20, 23, 280), (24, 26, 310)],
    },
    {
        "key": "yokohama_seaside_line_202504",
        "operatorIds": ["横浜シサイドライン"],
        "operatorName": "横浜シーサイドライン",
        "url": "https://www.seasideline.co.jp/fare_ticket/document/pass_rule.pdf",
        "notes": ["2025年4月1日最終改正の旅客営業規則第49条・大人片道普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_F66185DED59EAF"],
        "rows": [(1, 2, 240), (3, 4, 270), (5, 7, 300), (8, 11, 320)],
    },
    {
        "key": "odakyu",
        "operatorIds": ["odakyu"],
        "operatorName": "小田急電鉄",
        "url": "https://www.odakyu.jp/ticket/doc/passenger_operating_rules.pdf?202411=",
        "notes": [
            "旅客営業規則の別表第1号ロに定める片道普通旅客運賃（10円単位）に、第130条の鉄道駅バリアフリー料金10円を加算した大人普通運賃。",
        ],
        "rows": [(1, 3, 140), (4, 6, 170), (7, 9, 200), (10, 13, 230),
                 (14, 17, 270), (18, 21, 300), (22, 25, 330), (26, 29, 360),
                 (30, 33, 390), (34, 37, 430), (38, 41, 480), (42, 45, 520),
                 (46, 49, 560), (50, 56, 610), (57, 61, 650), (62, 66, 700),
                 (67, 71, 750), (72, 76, 800), (77, 81, 850), (82, 83, 910)],
    },
    {
        "key": "nagoya_subway",
        "operatorIds": ["名古屋市"],
        "operatorName": "名古屋市交通局",
        "url": "https://www.kotsu.city.nagoya.jp/rp/subway/trp0000172.htm",
        "notes": ["地下鉄普通料金・対キロ区間制。大人普通料金。"],
        "rows": [(1, 3, 210), (4, 7, 240), (8, 11, 270), (12, 15, 310), (16, 100, 340)],
    },
    {
        "key": "meitetsu",
        "operatorIds": ["名古屋鉄道"],
        "operatorName": "名古屋鉄道",
        "url": "https://www.mlit.go.jp/common/001625122.pdf",
        "notes": ["国土交通省の名古屋鉄道上限変更認可答申に掲載された鉄道及び軌道の普通旅客運賃。加算運賃は未適用。"],
        "rows": [(1, 3, 180), (4, 4, 210), (5, 7, 250), (8, 8, 270), (9, 12, 330),
                 (13, 16, 400), (17, 20, 460), (21, 24, 510), (25, 28, 570),
                 (29, 32, 630), (33, 36, 690), (37, 40, 750), (41, 44, 830),
                 (45, 48, 900), (49, 52, 980), (53, 56, 1050), (57, 60, 1120),
                 (61, 64, 1190), (65, 68, 1270), (69, 72, 1320), (73, 76, 1380),
                 (77, 80, 1430), (81, 85, 1500), (86, 90, 1550), (91, 95, 1610),
                 (96, 100, 1670), (101, 110, 1760), (111, 120, 1860),
                 (121, 130, 1950), (131, 143, 2050)],
    },
    {
        "key": "keihan",
        "operatorIds": ["京阪電気鉄道"],
        "operatorName": "京阪電気鉄道",
        "url": "https://www.keihan.co.jp/traffic/unchinkaitei_2025/pdf/sinsei_untin_2503.pdf",
        "notes": ["2025年10月1日以降の京阪線普通旅客運賃。大津線と鋼索線は別体系のため覆わない。中之島線・鴨東線加算運賃は未適用。"],
        "routeIds": [
            "V4_ROUTE_38DD56D836CA9B",
            "V4_ROUTE_00C97565E93E07",
            "V4_ROUTE_C08DBD032152FF",
            "V4_ROUTE_EBDE860162D6CA",
            "V4_ROUTE_CDC436D67C87AE",
        ],
        "rows": [(1, 3, 180), (4, 7, 240), (8, 12, 320), (13, 17, 360), (18, 22, 400),
                 (23, 28, 420), (29, 34, 440), (35, 40, 460), (41, 46, 480),
                 (47, 52, 490), (53, 54, 500)],
    },
    {
        "key": "nankai",
        "operatorIds": ["南海電気鉄道"],
        "operatorName": "南海電気鉄道",
        "url": "https://www.nankai.co.jp/lib/company/handbook/pdf/handbook2025.pdf",
        "notes": ["2025年4月1日改定の南海線及び高野線対キロ区間制。空港線加算運賃と鋼索線は未収集のため覆わない。"],
        "routeIds": [
            "V4_ROUTE_F60089BDD83AB8",
            "V4_ROUTE_B6CB90953DCB01",
            "V4_ROUTE_606F2D70D0B351",
            "V4_ROUTE_180A8AC3E9B282",
            "V4_ROUTE_CB287DAA293B22",
            "V4_ROUTE_3B2B50773C0B7A",
        ],
        "rows": [(1, 3, 180), (4, 7, 240), (8, 11, 290), (12, 15, 370), (16, 19, 420),
                 (20, 23, 490), (24, 27, 540), (28, 31, 610), (32, 35, 650),
                 (36, 39, 690), (40, 44, 740), (45, 49, 790), (50, 54, 850),
                 (55, 59, 880), (60, 64, 930), (65, 69, 970), (70, 74, 1010),
                 (75, 80, 1060), (81, 86, 1090), (87, 92, 1140), (93, 98, 1190),
                 (99, 104, 1230), (105, 110, 1280), (111, 116, 1320),
                 (117, 122, 1360), (123, 128, 1400)],
    },
    {
        "key": "hiroden_flat",
        "operatorIds": ["広島電鉄"],
        "operatorName": "広島電鉄",
        "url": "https://www.hiroden.co.jp/train/use/index.html",
        "notes": ["2025年2月1日以降の電車全線均一普通運賃。"],
        "rows": [(1, None, 240)],
    },
    {
        "key": "kumamoto_city_tram_flat",
        "operatorIds": ["熊本市"],
        "operatorName": "熊本市交通局",
        "url": "https://www.kotsu-kumamoto.jp/one_html3/pub/Default.aspx?c_id=63",
        "notes": ["熊本市電の均一普通運賃。"],
        "rows": [(1, None, 200)],
    },
    {
        "key": "nagasaki_tram_flat",
        "operatorIds": ["長崎電気軌道"],
        "operatorName": "長崎電気軌道",
        "url": "https://wwwtb.mlit.go.jp/kyushu/content/000339858.pdf",
        "notes": ["2025年4月1日以降の路面電車均一普通運賃。"],
        "rows": [(1, None, 150)],
    },
    {
        "key": "kagoshima_city_tram_flat",
        "operatorIds": ["鹿児島市"],
        "operatorName": "鹿児島市交通局",
        "url": "https://www.kotsu-city-kagoshima.jp/kensaku/service/",
        "notes": ["鹿児島市電の全線均一普通運賃。2026年8月予定改定は未反映。"],
        "rows": [(1, None, 170)],
    },
    {
        "key": "sapporo_streetcar_flat",
        "operatorIds": ["一般社団法人札幌市交通事業振興公社"],
        "operatorName": "札幌市交通事業振興公社",
        "url": "https://www.stsp.or.jp/business/streetcar/price/",
        "notes": ["札幌市電の路面電車のみの均一普通運賃。"],
        "rows": [(1, None, 230)],
    },
    {
        "key": "hankai_flat",
        "operatorIds": ["阪堺電気軌道"],
        "operatorName": "阪堺電気軌道",
        "url": "https://hankai.co.jp/howto/",
        "notes": ["阪堺電車の全線均一普通運賃。"],
        "rows": [(1, None, 240)],
    },
    {
        "key": "keifuku_randen_flat",
        "operatorIds": ["京福電気鉄道"],
        "operatorName": "京福電気鉄道",
        "url": "https://www.keifuku.co.jp/cms/randen_ticket/",
        "notes": ["嵐電の全線均一普通運賃。鋼索線には適用しない。"],
        "routeIds": ["V4_ROUTE_BFA60A933F4F9C", "V4_ROUTE_DB2AD60B184594"],
        "rows": [(1, None, 250)],
    },
    {
        "key": "toyama_city_tram_flat",
        "operatorIds": ["富山地方鉄道"],
        "operatorName": "富山地方鉄道",
        "url": "https://www.chitetsu.co.jp/?page_id=656",
        "notes": ["富山地方鉄道市内電車の均一普通運賃。鉄道線には適用しない。"],
        "routeIds": [
            "V4_ROUTE_995723E634D6E3",
            "V4_ROUTE_38576359B4D802",
            "V4_ROUTE_4DD2A4208FD859",
            "V4_ROUTE_F91BC93A7D5672",
            "V4_ROUTE_D9FC6FE006783D",
            "V4_ROUTE_0333A9400A6D09",
        ],
        "rows": [(1, None, 240)],
    },
    {
        "key": "toyama_chitetsu_rail_202504",
        "operatorIds": ["富山地方鉄道"],
        "operatorName": "富山地方鉄道",
        "url": "https://m.chitetsu.co.jp/wp-content/uploads/2025/03/57f926382b6e9c826ae79da324e7afe6.pdf",
        "notes": ["2025年4月1日改定の鉄道線普通旅客運賃（対キロ区間制）。市内電車は別表で覆う。"],
        "routeIds": [
            "V4_ROUTE_5FFA88A8BE3B1E",
            "V4_ROUTE_F7B8284C459AB2",
            "V4_ROUTE_B2C1AF1BE22620",
            "V4_ROUTE_A54E9A4FFCFC02",
        ],
        "rows": [
            (1, 3, 240), (4, 6, 360), (7, 9, 480), (10, 12, 600),
            (13, 15, 740), (16, 18, 840), (19, 21, 960), (22, 24, 1080),
            (25, 27, 1200), (28, 30, 1300), (31, 33, 1420), (34, 36, 1520),
            (37, 39, 1620), (40, 42, 1720), (43, 45, 1820), (46, 48, 1920),
            (49, 51, 2020), (52, 54, 2160), (55, 57, 2200), (58, 60, 2260),
            (61, 63, 2300), (64, 66, 2360), (67, 68, 2460),
        ],
    },
    {
        "key": "hakodate_city_tram",
        "operatorIds": ["函館市"],
        "operatorName": "函館市企業局交通部",
        "url": "https://www.city.hakodate.hokkaido.jp/docs/2014012100946/",
        "notes": ["2025年12月1日改定の函館市電普通乗車料金。対キロ区間制の大人運賃。"],
        "routeIds": [
            "V4_ROUTE_F1E341DE8C7E9D",
            "V4_ROUTE_4667B5278AA5D2",
            "V4_ROUTE_A28A9834D3C251",
            "V4_ROUTE_88D58E5C03EE56",
        ],
        "rows": [(1, 2, 250), (3, 4, 270), (5, 7, 290), (8, None, 300)],
    },
    {
        "key": "iyotetsu_city_tram_flat",
        "operatorIds": ["伊予鉄道"],
        "operatorName": "伊予鉄道",
        "url": "https://www.iyotetsu.co.jp/sp/topics/26/0401.html",
        "notes": [
            "2026年4月1日改定の市内電車現金大人均一運賃。郊外電車は駅相互間の三角表体系のためこの表では覆わない。",
        ],
        "routeIds": [
            "V4_ROUTE_FEFBD30974CC88",
            "V4_ROUTE_E00F3A4F3ADDDB",
            "V4_ROUTE_D284BA6E2F031D",
            "V4_ROUTE_5796C85F95E58B",
            "V4_ROUTE_7A9461E7F67716",
            "V4_ROUTE_38603FF7472321",
        ],
        "rows": [(1, None, 250)],
    },
    {
        "key": "toyotetsu_city_tram_flat",
        "operatorIds": ["豊橋鉄道"],
        "operatorName": "豊橋鉄道",
        "url": "https://www.toyotetsu.com/shinaisen/charges.html",
        "notes": ["豊橋鉄道市内線（東田本線）の大人均一運賃。渥美線は別体系のためこの表では覆わない。"],
        "routeIds": ["V4_ROUTE_84FDC3869098B6"],
        "rows": [(1, None, 200)],
    },
    {
        "key": "entetsu_railway_202404",
        "operatorIds": ["遠州鉄道"],
        "operatorName": "遠州鉄道",
        "url": "https://www.entetsu.co.jp/tetsudou/fare/pdf/pdf_fare.pdf",
        "notes": ["2024年4月1日実施の鉄道線普通旅客運賃及びキロ程表。大人普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_20C2E770E78BE9"],
        "rows": [(1, 4, 160), (5, 5, 190), (6, 6, 220), (7, 7, 250),
                 (8, 8, 270), (9, 9, 310), (10, 10, 330), (11, 11, 350),
                 (12, 12, 380), (13, 13, 400), (14, 14, 420), (15, 15, 450),
                 (16, 16, 470), (17, 17, 490), (18, 18, 510)],
    },
    {
        "key": "shizutetsu_railway_202304",
        "operatorIds": ["静岡鉄道"],
        "operatorName": "静岡鉄道",
        "url": "https://train.shizutetsu.co.jp/wp-content/uploads/2023/04/%E6%97%85%E5%AE%A2%E9%81%8B%E8%B3%83%E3%81%AE%E8%A8%88%E7%AE%97%E6%96%B9%E6%B3%95%E5%8F%8A%E3%81%B2%E3%82%99%E9%81%A9%E7%94%A8%E6%96%B9%E6%B3%95.pdf",
        "notes": ["2023年4月1日改定の静岡鉄道普通旅客運賃計算方。対キロ区間制の大人普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_69ABFF25F532A2"],
        "rows": [(1, 2, 160), (3, 4, 170), (5, 5, 190), (6, 6, 220),
                 (7, 7, 240), (8, 8, 270), (9, 9, 300), (10, 10, 330),
                 (11, 11, 350)],
    },
    {
        "key": "hokuhoku_railway_202604",
        "operatorIds": ["北越急行"],
        "operatorName": "北越急行",
        "url": "https://hokuhoku.co.jp/pdf/eigyo/table1.pdf",
        "notes": ["北越急行旅客営業規則別表第1号の大人片道普通旅客運賃。1kmごとの公式表を同額区間に圧縮。"],
        "routeIds": ["V4_ROUTE_D3C28A773BCC73"],
        "rows": [(1, 3, 210), (4, 6, 240), (7, 9, 260), (10, 12, 300),
                 (13, 15, 350), (16, 18, 400), (19, 21, 470), (22, 24, 550),
                 (25, 27, 640), (28, 30, 720), (31, 33, 800), (34, 36, 890),
                 (37, 39, 970), (40, 42, 1020), (43, 45, 1080), (46, 48, 1130),
                 (49, 51, 1190), (52, 54, 1230), (55, 57, 1270), (58, 60, 1310)],
    },
    {
        "key": "saitama_railway",
        "operatorIds": ["saitama_railway"],
        "operatorName": "埼玉高速鉄道",
        "url": "https://www.s-rail.co.jp/ticket/info/",
        "notes": ["埼玉高速鉄道公式のキロ別普通旅客運賃。"],
        "routeIds": ["V4_ROUTE_787615FAEEC907"],
        "rows": [(1, 3, 210), (4, 5, 270), (6, 7, 310), (8, 9, 350),
                 (10, 11, 400), (12, 13, 440), (14, 15, 480)],
    },
    {
        "key": "iga_railway",
        "operatorIds": ["伊賀鉄道"],
        "operatorName": "伊賀鉄道",
        "url": "https://www.igatetsu.co.jp/datawp/unchin/pdf/20250201_unchin.pdf",
        "notes": ["2025年2月1日改定の伊賀鉄道普通運賃表。大人普通運賃。"],
        "routeIds": ["V4_ROUTE_FCC18193CE8DC9"],
        "rows": [(1, 3, 220), (4, 6, 280), (7, 10, 330), (11, 14, 400), (15, None, 450)],
    },
    {
        "key": "yamaman_yukarigaoka_flat",
        "operatorIds": ["山万"],
        "operatorName": "山万",
        "url": "https://town.yukarigaoka.jp/yukariline/fare/",
        "notes": ["山万ユーカリが丘線の普通乗車券均一大人運賃。"],
        "routeIds": ["V4_ROUTE_D79F266E74EE99"],
        "rows": [(1, None, 200)],
    },
    {
        "key": "disney_resort_line_flat",
        "operatorIds": ["舞浜リゾトライン"],
        "operatorName": "舞浜リゾートライン",
        "url": "https://www.tokyodisneyresort.jp/tdr/resortline/fare.html",
        "notes": ["ディズニーリゾートラインの普通乗車券均一大人運賃。"],
        "routeIds": ["V4_ROUTE_D17798F2575CB0"],
        "rows": [(1, None, 300)],
    },
    {
        "key": "takao_tozan_cable_flat",
        "operatorIds": ["高尾登山電鉄"],
        "operatorName": "高尾登山電鉄",
        "url": "https://www.takaotozan.co.jp/timeprice/?vm=r",
        "notes": ["高尾山ケーブルカー普通旅客運賃。リフトも同額だが、v4 route は鋼索線のみを覆う。"],
        "routeIds": ["V4_ROUTE_B74E1B273832D9"],
        "rows": [(1, None, 490)],
    },
    {
        "key": "tsukuba_cable_flat",
        "operatorIds": ["筑波観光鉄道"],
        "operatorName": "筑波観光鉄道",
        "url": "https://mt-tsukuba.com/cablecar-fare/",
        "notes": ["筑波山ケーブルカー普通片道大人運賃。"],
        "routeIds": ["V4_ROUTE_EDA95EE10345C5"],
        "rows": [(1, None, 590)],
    },
    {
        "key": "mitake_cable_flat",
        "operatorIds": ["御岳登山鉄道"],
        "operatorName": "御岳登山鉄道",
        "url": "https://www.mitaketozan.co.jp/timetable.html",
        "notes": ["御岳登山鉄道ケーブルカー運賃の普通片道大人運賃。"],
        "routeIds": ["V4_ROUTE_46512B60E1D0DF"],
        "rows": [(1, None, 600)],
    },
    {
        "key": "jukkoku_cable_flat",
        "operatorIds": ["十国峠"],
        "operatorName": "十国峠",
        "url": "https://www.jukkoku-cable.jp/guide/index.html",
        "notes": ["十国峠パノラマケーブルカー普通片道おとな運賃。"],
        "routeIds": ["V4_ROUTE_4CD50E3AFF2F0F"],
        "rows": [(1, None, 370)],
    },
    {
        "key": "amanohashidate_cable_flat",
        "operatorIds": ["丹後海陸交通"],
        "operatorName": "丹後海陸交通",
        "url": "https://www.tankai.jp/trip/cable/",
        "notes": ["天橋立ケーブルカー府中-傘松間の普通片道大人運賃。"],
        "routeIds": ["V4_ROUTE_BDF24746541A78"],
        "rows": [(1, None, 400)],
    },
    {
        "key": "yurikamome",
        "operatorIds": ["yurikamome"],
        "operatorName": "ゆりかもめ",
        "url": "https://www.yurikamome.co.jp/company/news/b405570a69e5124744dcf7b90db48d69.pdf",
        "notes": ["2019年10月1日改定の普通旅客運賃・きっぷ10円単位。"],
        "routeIds": ["V4_ROUTE_4852C183FDA4E3"],
        "rows": [(1, 2, 190), (3, 5, 260), (6, 8, 330), (9, 15, 390)],
    },
    {
        "key": "tsukuba_express",
        "operatorIds": ["tsukuba_express"],
        "operatorName": "首都圏新都市鉄道",
        "url": "https://www.mir.co.jp/company/260129%E8%A8%82%E6%AD%A3%EF%BC%88HP%E6%8C%BF%E5%85%A5%E7%94%A8%EF%BC%89%E9%81%8B%E8%B3%83%E8%A1%A8.pdf",
        "notes": ["2026年3月14日改定の普通旅客運賃・きっぷ10円単位。"],
        "routeIds": ["V4_ROUTE_988834EF8B1E1B"],
        "rows": [
            (1, 3, 180), (4, 5, 230), (6, 7, 280), (8, 9, 320), (10, 11, 370),
            (12, 13, 420), (14, 15, 460), (16, 18, 520), (19, 21, 580),
            (22, 24, 630), (25, 27, 690), (28, 30, 750), (31, 33, 800),
            (34, 36, 860), (37, 39, 920), (40, 42, 970), (43, 45, 1020),
            (46, 48, 1070), (49, 51, 1130), (52, 54, 1180), (55, 57, 1230),
            (58, 59, 1280),
        ],
    },
    {
        "key": "okayama_tram_flat",
        "operatorIds": ["岡山電気軌道"],
        "operatorName": "岡山電気軌道",
        "url": "https://okayama-kido.co.jp/tram/route-map/",
        "notes": ["2025年10月1日以降の路面電車均一普通運賃。"],
        "rows": [(1, None, 160)],
    },
    {
        "key": "kyoto_subway",
        "operatorIds": ["京都市"],
        "operatorName": "京都市交通局",
        "url": "https://www2.city.kyoto.lg.jp/kotsu/webguide/ja/fare/fare_tika.html",
        "notes": ["2025年10月1日以降の京都市営地下鉄普通運賃。"],
        "rows": [(1, 3, 220), (4, 7, 260), (8, 11, 290), (12, 15, 330), (16, None, 360)],
    },
    {
        "key": "fukuoka_subway",
        "operatorIds": ["福岡市"],
        "operatorName": "福岡市交通局",
        "url": "https://wwwtb.mlit.go.jp/kyushu/content/000292685.pdf",
        "notes": ["福岡市交通局の鉄道事業旅客運賃上限認可に掲載された普通旅客運賃。地下鉄線内のみ。"],
        "routeIds": [
            "V4_ROUTE_6FF36BFBC5E2E4",
            "V4_ROUTE_1A8E71DAEB4039",
            "V4_ROUTE_36774E88402A92",
        ],
        "rows": [(1, 3, 210), (4, 7, 260), (8, 11, 300), (12, 15, 340), (16, 19, 360), (20, None, 380)],
    },
    {
        "key": "yokohama_subway",
        "operatorIds": ["横浜市"],
        "operatorName": "横浜市交通局",
        "url": "https://cgi.city.yokohama.lg.jp/somu/reiki/reiki_honbun/g202RG00001028.html",
        "notes": ["横浜市高速鉄道運賃条例施行規程の対距離区間制普通旅客運賃。"],
        "routeIds": [
            "V4_ROUTE_A8BD427A645483",
            "V4_ROUTE_82D3CC039ED231",
            "V4_ROUTE_9BA969C02A294C",
        ],
        "rows": [(1, 3, 210), (4, 7, 250), (8, 11, 280), (12, 15, 310),
                 (16, 19, 340), (20, 23, 370), (24, 27, 400), (28, 31, 430),
                 (32, 35, 470), (36, 39, 500), (40, 43, 530), (44, None, 560)],
    },
    {
        "key": "kobe_subway_regular",
        "operatorIds": ["神戸市"],
        "operatorName": "神戸市交通局",
        "url": "https://kotsu.city.kobe.lg.jp/wp-content/uploads/02_/pdf/shosainoryokinhyo_202602.pdf",
        "notes": ["神戸市営地下鉄の詳細料金表に掲載された区数別普通料金。北神線は特殊区分を含むためこの表では覆わない。"],
        "routeIds": [
            "V4_ROUTE_E2BA35762A80F5",
            "V4_ROUTE_8A5786350C3583",
            "V4_ROUTE_49BC2A9E27C46A",
            "V4_ROUTE_F0090106DB1184",
        ],
        "rows": [(1, 3, 210), (4, 7, 240), (8, 10, 280), (11, 13, 310),
                 (14, 16, 350), (17, 19, 380), (20, 23, 410), (24, 27, 440),
                 (28, None, 470)],
    },
    {
        "key": "sapporo_subway",
        "operatorIds": ["札幌市"],
        "operatorName": "札幌市交通局",
        "url": "https://www.city.sapporo.jp/st/josyaken/ryokin/ryoukin.html",
        "notes": ["2026年4月1日更新の札幌市営地下鉄単独料金表。マル2区は地下鉄単独では2区と同額。"],
        "routeIds": [
            "V4_ROUTE_434B8D33E5E9AA",
            "V4_ROUTE_1793C79C77C546",
            "V4_ROUTE_6258C3B0ADC443",
        ],
        "rows": [(1, 3, 210), (4, 7, 250), (8, 11, 290), (12, 15, 330),
                 (16, 19, 360), (20, 21, 380)],
    },
    {
        "key": "nose_railway",
        "operatorIds": ["能勢電鉄"],
        "operatorName": "能勢電鉄",
        "url": "https://noseden.hankyu.co.jp/ticket/overview.html",
        "notes": [
            "2025年1月19日改定の普通運賃・営業キロ程表から大人普通運賃を整理。営業キロ程の1キロ未満は切り上げ。",
        ],
        "routeIds": [
            "V4_ROUTE_A1600E265C3FC2",
            "V4_ROUTE_C7BD253DAE1CBD",
        ],
        "rows": [(1, 2, 180), (3, 4, 220), (5, 6, 260), (7, 8, 300),
                 (9, 10, 320), (11, 12, 350), (13, None, 360)],
    },
    {
        "key": "heichiku_regular",
        "operatorIds": ["平成筑豊鉄道"],
        "operatorName": "平成筑豊鉄道",
        "url": "https://www.heichiku.net/heichiku/corp/",
        "notes": [
            "会社概要の普通旅客運賃（対キロ区間制）に掲載された2025年10月18日改定後の大人普通運賃。門司港レトロ観光線は別体系。",
        ],
        "routeIds": [
            "V4_ROUTE_F6A67794050DD3",
            "V4_ROUTE_160F838832EA21",
            "V4_ROUTE_8514D7B051C091",
        ],
        "rows": [(1, 3, 270), (4, 6, 340), (7, 9, 400), (10, 12, 450),
                 (13, 15, 500), (16, 18, 560), (19, 21, 620), (22, 24, 700),
                 (25, 27, 770), (28, 30, 840), (31, 33, 930), (34, 36, 1000),
                 (37, 39, 1060), (40, 42, 1120), (43, 43, 1190)],
    },
    {
        "key": "nishitetsu_202604",
        "operatorIds": ["西日本鉄道"],
        "operatorName": "西日本鉄道",
        "url": "https://www.nishitetsu.jp/train/2026_unchin-kaitei-ninka/",
        "notes": ["2026年4月1日実施の鉄道運賃改定後の普通旅客運賃（大人）。"],
        "rows": [
            (1, 3, 180), (4, 6, 240), (7, 9, 300), (10, 13, 360),
            (14, 17, 420), (18, 21, 480), (22, 26, 540), (27, 31, 600),
            (32, 36, 660), (37, 41, 720), (42, 46, 780), (47, 51, 840),
            (52, 56, 900), (57, 61, 960), (62, 66, 1020), (67, 71, 1080),
            (72, 75, 1140),
        ],
    },
    {
        "key": "amagi_railway_202410",
        "operatorIds": ["甘木鉄道"],
        "operatorName": "甘木鉄道",
        "url": "https://www.amatetsu.jp/new/20240917_info.pdf",
        "notes": [
            "甘木鉄道公式の2024年10月1日鉄道旅客運賃改定資料に掲載された普通旅客運賃（大人、片道）の改定後運賃。",
        ],
        "routeIds": ["V4_ROUTE_9F8733701EB54D"],
        "rows": [
            (1, 1, 140),
            (2, 2, 200),
            (3, 4, 250),
            (5, 6, 290),
            (7, 8, 340),
            (9, 10, 380),
            (11, 12, 410),
            (13, 14, 430),
        ],
    },
]

def station_pair_triangle_rows(
    station_order: list[str],
    fare_rows: list[tuple[str, list[int]]],
) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for row_station, fares in fare_rows:
        row_index = station_order.index(row_station)
        if len(fares) != row_index:
            raise ValueError(f"{row_station} fare row has {len(fares)} fares, expected {row_index}")
        for previous_station, yen in zip(station_order[:row_index], fares, strict=True):
            pairs.append((previous_station, row_station, yen))
    return pairs


MANUAL_STATION_PAIR_FARE_TABLES: list[dict[str, Any]] = [
    {
        "key": "hitachinaka_seaside_station_pairs_202110",
        "operatorIds": ["ひたちなか海浜鉄道"],
        "operatorName": "ひたちなか海浜鉄道",
        "url": "https://www.hitachinaka-rail.co.jp/timetable/fare_2021.pdf",
        "notes": [
            "湊線公式の普通旅客運賃表（2021年10月時点）から大人普通運賃の三角表を転記。公式サイトは証明書ホスト名不一致のため、自動取得ではfetchErrorが残る場合がある。",
        ],
        "routeIds": ["V4_ROUTE_F074EB68F3A583"],
        "pairs": station_pair_triangle_rows(
            ["勝田", "工機前", "金上", "中根", "高田の鉄橋", "那珂湊", "殿山", "平磯", "美乃浜学園", "磯崎", "阿字ヶ浦"],
            [
                ("工機前", [150]),
                ("金上", [150, 150]),
                ("中根", [150, 190, 190]),
                ("高田の鉄橋", [150, 230, 260, 310]),
                ("那珂湊", [150, 150, 260, 310, 350]),
                ("殿山", [150, 150, 190, 310, 350, 380]),
                ("平磯", [150, 150, 150, 230, 350, 420, 420]),
                ("美乃浜学園", [150, 150, 190, 230, 310, 420, 460, 490]),
                ("磯崎", [150, 150, 150, 230, 260, 350, 460, 490, 530]),
                ("阿字ヶ浦", [150, 150, 150, 190, 260, 310, 380, 490, 530, 570]),
            ],
        ),
    },
    {
        "key": "isumi_railway_station_pairs_202403",
        "operatorIds": ["いすみ鉄道"],
        "operatorName": "いすみ鉄道",
        "url": "https://isumirail.co.jp/wp-content/uploads/2024/03/v4_2024timetable_weekdays.pdf",
        "notes": [
            "いすみ鉄道公式時刻表PDF内の普通旅客運賃表（2024年3月16日改正、2019年10月1日運賃改定）から大人普通運賃の三角表を転記。",
        ],
        "routeIds": ["V4_ROUTE_EE9C2D1EA2F7E1"],
        "pairs": station_pair_triangle_rows(
            ["大原", "西大原", "上総東", "新田野", "国吉", "上総中川", "城見ヶ丘", "大多喜", "小谷松", "東総元", "久我原", "総元", "西畑", "上総中野"],
            [
                ("西大原", [190]),
                ("上総東", [260, 260]),
                ("新田野", [330, 260, 190]),
                ("国吉", [330, 330, 260, 190]),
                ("上総中川", [410, 410, 330, 260, 260]),
                ("城見ヶ丘", [480, 480, 410, 330, 260, 190]),
                ("大多喜", [550, 480, 410, 330, 330, 260, 190]),
                ("小谷松", [610, 550, 480, 410, 410, 330, 260, 190]),
                ("東総元", [610, 550, 480, 480, 410, 330, 260, 260, 190]),
                ("久我原", [610, 610, 550, 480, 410, 330, 260, 260, 190, 190]),
                ("総元", [670, 610, 550, 480, 480, 410, 330, 330, 260, 190, 190]),
                ("西畑", [730, 670, 610, 550, 550, 480, 410, 410, 330, 260, 260, 190]),
                ("上総中野", [730, 730, 670, 610, 550, 480, 410, 410, 330, 330, 260, 260, 190]),
            ],
        ),
    },
    {
        "key": "gakunan_railway_station_pairs_202310",
        "operatorIds": ["岳南電車"],
        "operatorName": "岳南電車",
        "url": "https://www.gakutetsu.jp/fare/fare.html",
        "notes": [
            "岳南電車公式サイトの2023年10月1日からの通常運賃表から大人普通運賃の駅間表を転記。",
        ],
        "routeIds": ["V4_ROUTE_D9093DEF85655F"],
        "pairs": station_pair_triangle_rows(
            ["吉原", "ジヤトコ前", "吉原本町", "本吉原", "岳南原田", "比奈", "岳南富士岡", "須津", "神谷", "岳南江尾"],
            [
                ("ジヤトコ前", [220]),
                ("吉原本町", [220, 170]),
                ("本吉原", [220, 170, 170]),
                ("岳南原田", [260, 220, 170, 170]),
                ("比奈", [260, 220, 220, 220, 170]),
                ("岳南富士岡", [310, 260, 220, 220, 170, 170]),
                ("須津", [310, 260, 260, 260, 220, 170, 170]),
                ("神谷", [370, 260, 260, 260, 220, 220, 170, 170]),
                ("岳南江尾", [370, 310, 310, 310, 260, 220, 220, 170, 170]),
            ],
        ),
    },
    {
        "key": "alpico_kamikochi_station_pairs_201910",
        "operatorIds": ["アルピコ交通"],
        "operatorName": "アルピコ交通",
        "url": "https://www.alpico.co.jp/traffic/datas/files/2023/05/19/6b13910046da240bbe66ff3a0f194c4bddeb4c68.pdf",
        "notes": [
            "アルピコ交通公式の上高地線電車駅間普通旅客運賃表（2019年10月1日改定）から大人片道運賃を転記。",
        ],
        "routeIds": ["V4_ROUTE_7738E08E9AF7E4"],
        "pairs": station_pair_triangle_rows(
            ["新島々", "渕東", "波田", "下島", "森口", "三溝", "新村", "北新・松本大学前", "下新", "大庭", "信濃荒井", "渚", "西松本", "松本"],
            [
                ("渕東", [180]),
                ("波田", [180, 200]),
                ("下島", [180, 200, 250]),
                ("森口", [180, 180, 250, 310]),
                ("三溝", [180, 180, 200, 310, 360]),
                ("新村", [180, 180, 200, 250, 360, 460]),
                ("北新・松本大学前", [180, 180, 200, 250, 310, 410, 460]),
                ("下新", [180, 180, 200, 250, 310, 360, 460, 500]),
                ("大庭", [180, 180, 200, 250, 310, 360, 460, 550, 590]),
                ("信濃荒井", [180, 180, 200, 250, 310, 360, 410, 500, 550, 630]),
                ("渚", [180, 180, 200, 250, 310, 360, 410, 460, 500, 590, 670]),
                ("西松本", [180, 180, 180, 200, 250, 310, 410, 460, 500, 550, 630, 670]),
                ("松本", [180, 180, 180, 180, 250, 310, 360, 410, 460, 500, 590, 630, 710]),
            ],
        ),
    },
    {
        "key": "kita_osaka_kyuko_station_pairs",
        "operatorIds": ["北大阪急行電鉄"],
        "operatorName": "北大阪急行電鉄",
        "url": "https://www.kita-kyu.co.jp/wp/wp-content/uploads/2023/08/enshinfares.pdf",
        "notes": [
            "北大阪急行公式の南北線延伸線開業後普通券運賃表。箕面萱野・箕面船場阪大前の運賃は加算運賃込み。",
        ],
        "routeIds": ["V4_ROUTE_F54A44B56FBA97"],
        "pairs": [
            ("箕面萱野", "箕面船場阪大前", 160),
            ("箕面萱野", "千里中央", 190),
            ("箕面萱野", "桃山台", 200),
            ("箕面萱野", "緑地公園", 220),
            ("箕面萱野", "江坂", 240),
            ("箕面船場阪大前", "千里中央", 160),
            ("箕面船場阪大前", "桃山台", 190),
            ("箕面船場阪大前", "緑地公園", 200),
            ("箕面船場阪大前", "江坂", 220),
            ("千里中央", "桃山台", 100),
            ("千里中央", "緑地公園", 130),
            ("千里中央", "江坂", 140),
            ("桃山台", "緑地公園", 100),
            ("桃山台", "江坂", 130),
            ("緑地公園", "江坂", 100),
        ],
    },
    {
        "key": "oyama_cable_station_pairs",
        "operatorIds": ["大山観光電鉄"],
        "operatorName": "大山観光電鉄",
        "url": "https://www.ooyama-cable.co.jp/timetable/",
        "notes": [
            "大山ケーブルカー普通片道大人運賃。中間駅までと始発終点間の全3駅ペア。",
        ],
        "routeIds": ["V4_ROUTE_B9B9AABDAB4D38"],
        "pairs": [
            ("大山ケーブル", "大山寺", 360),
            ("大山寺", "阿夫利神社", 360),
            ("大山ケーブル", "阿夫利神社", 640),
        ],
    },
    {
        "key": "shonan_monorail_station_pairs_202603",
        "operatorIds": ["湘南モノレル"],
        "operatorName": "湘南モノレール",
        "url": "https://www.shonan-monorail.co.jp/ticket/",
        "notes": ["2026年3月14日改定の各駅普通旅客運賃表から大人普通運賃を転記。"],
        "routeIds": ["V4_ROUTE_1478E287C522FF"],
        "pairs": [
            ("大船", "富士見町", 220),
            ("大船", "湘南町屋", 220),
            ("大船", "湘南深沢", 240),
            ("大船", "西鎌倉", 290),
            ("大船", "片瀬山", 320),
            ("大船", "目白山下", 340),
            ("大船", "湘南江の島", 340),
            ("富士見町", "湘南町屋", 220),
            ("富士見町", "湘南深沢", 220),
            ("富士見町", "西鎌倉", 260),
            ("富士見町", "片瀬山", 290),
            ("富士見町", "目白山下", 320),
            ("富士見町", "湘南江の島", 320),
            ("湘南町屋", "湘南深沢", 220),
            ("湘南町屋", "西鎌倉", 240),
            ("湘南町屋", "片瀬山", 260),
            ("湘南町屋", "目白山下", 290),
            ("湘南町屋", "湘南江の島", 290),
            ("湘南深沢", "西鎌倉", 240),
            ("湘南深沢", "片瀬山", 240),
            ("湘南深沢", "目白山下", 260),
            ("湘南深沢", "湘南江の島", 260),
            ("西鎌倉", "片瀬山", 220),
            ("西鎌倉", "目白山下", 220),
            ("西鎌倉", "湘南江の島", 220),
            ("片瀬山", "目白山下", 220),
            ("片瀬山", "湘南江の島", 220),
            ("目白山下", "湘南江の島", 220),
        ],
    },
    {
        "key": "hanshin_kobe_kosoku_station_pairs_202603",
        "operatorIds": ["阪神電気鉄道"],
        "operatorName": "阪神電気鉄道",
        "url": "https://www.hanshin.co.jp/ticket/yakkan/pdf/kousoku-passenger.pdf",
        "notes": ["2026年3月18日現在の高速線旅客営業規則別表第1号・駅間普通旅客運賃表。"],
        "routeIds": ["V4_ROUTE_024EE571AAF472"],
        "pairs": [
            ("西代", "高速長田", 140),
            ("西代", "大開", 140),
            ("西代", "新開地", 140),
            ("西代", "高速神戸", 160),
            ("西代", "花隈", 160),
            ("西代", "神戸三宮", 160),
            ("西代", "西元町", 160),
            ("西代", "元町", 160),
            ("西代", "湊川", 160),
            ("高速長田", "大開", 140),
            ("高速長田", "新開地", 140),
            ("高速長田", "高速神戸", 140),
            ("高速長田", "花隈", 160),
            ("高速長田", "神戸三宮", 160),
            ("高速長田", "西元町", 160),
            ("高速長田", "元町", 160),
            ("高速長田", "湊川", 140),
            ("大開", "新開地", 140),
            ("大開", "高速神戸", 140),
            ("大開", "花隈", 140),
            ("大開", "神戸三宮", 160),
            ("大開", "西元町", 140),
            ("大開", "元町", 160),
            ("大開", "湊川", 140),
            ("新開地", "高速神戸", 140),
            ("新開地", "花隈", 140),
            ("新開地", "神戸三宮", 140),
            ("新開地", "西元町", 140),
            ("新開地", "元町", 140),
            ("新開地", "湊川", 140),
            ("高速神戸", "花隈", 140),
            ("高速神戸", "神戸三宮", 140),
            ("高速神戸", "西元町", 140),
            ("高速神戸", "元町", 140),
            ("高速神戸", "湊川", 140),
            ("花隈", "神戸三宮", 140),
            ("花隈", "西元町", 140),
            ("花隈", "元町", 140),
            ("花隈", "湊川", 140),
            ("神戸三宮", "西元町", 140),
            ("神戸三宮", "元町", 160),
            ("神戸三宮", "湊川", 160),
            ("西元町", "元町", 140),
            ("西元町", "湊川", 140),
            ("元町", "湊川", 140),
        ],
    },
    {
        "key": "toyo_rapid_station_pairs_201910",
        "operatorIds": ["東葉高速鉄道"],
        "operatorName": "東葉高速鉄道",
        "url": "https://www.toyokosoku.co.jp/ticket/regular",
        "notes": ["東葉高速鉄道公式きっぷ案内の2019年10月1日改定・普通旅客運賃表。"],
        "routeIds": ["V4_ROUTE_64CF7E42A3196B"],
        "pairs": [
            ("西船橋", "東海神", 210),
            ("西船橋", "飯山満", 370),
            ("西船橋", "北習志野", 440),
            ("西船橋", "船橋日大前", 520),
            ("西船橋", "八千代緑が丘", 520),
            ("西船橋", "八千代中央", 580),
            ("西船橋", "村上", 640),
            ("西船橋", "東葉勝田台", 640),
            ("東海神", "飯山満", 300),
            ("東海神", "北習志野", 370),
            ("東海神", "船橋日大前", 440),
            ("東海神", "八千代緑が丘", 440),
            ("東海神", "八千代中央", 580),
            ("東海神", "村上", 580),
            ("東海神", "東葉勝田台", 640),
            ("飯山満", "北習志野", 210),
            ("飯山満", "船橋日大前", 300),
            ("飯山満", "八千代緑が丘", 300),
            ("飯山満", "八千代中央", 440),
            ("飯山満", "村上", 520),
            ("飯山満", "東葉勝田台", 520),
            ("北習志野", "船橋日大前", 210),
            ("北習志野", "八千代緑が丘", 210),
            ("北習志野", "八千代中央", 370),
            ("北習志野", "村上", 440),
            ("北習志野", "東葉勝田台", 440),
            ("船橋日大前", "八千代緑が丘", 210),
            ("船橋日大前", "八千代中央", 300),
            ("船橋日大前", "村上", 370),
            ("船橋日大前", "東葉勝田台", 370),
            ("八千代緑が丘", "八千代中央", 210),
            ("八千代緑が丘", "村上", 300),
            ("八千代緑が丘", "東葉勝田台", 370),
            ("八千代中央", "村上", 210),
            ("八千代中央", "東葉勝田台", 210),
            ("村上", "東葉勝田台", 210),
        ],
    },
    {
        "key": "minatomirai_station_pairs_202303",
        "operatorIds": ["横浜高速鉄道"],
        "operatorName": "横浜高速鉄道",
        "url": "https://www.mm21railway.co.jp/info/ticket.html?mode=pc",
        "notes": ["2023年3月18日改定のみなとみらい線公式普通旅客運賃（きっぷ利用、大人）。"],
        "routeIds": ["V4_ROUTE_848E30149914C1"],
        "pairs": [
            ("横浜", "新高島", 200),
            ("横浜", "みなとみらい", 200),
            ("横浜", "馬車道", 200),
            ("横浜", "日本大通り", 230),
            ("横浜", "元町・中華街", 230),
            ("新高島", "みなとみらい", 200),
            ("新高島", "馬車道", 200),
            ("新高島", "日本大通り", 200),
            ("新高島", "元町・中華街", 230),
            ("みなとみらい", "馬車道", 200),
            ("みなとみらい", "日本大通り", 200),
            ("みなとみらい", "元町・中華街", 200),
            ("馬車道", "日本大通り", 200),
            ("馬車道", "元町・中華街", 200),
            ("日本大通り", "元町・中華街", 200),
        ],
    },
    {
        "key": "mizuma_railway_station_pairs_202404",
        "operatorIds": ["水間鉄道"],
        "operatorName": "水間鉄道",
        "url": "https://www.suitetsu.com/train/fares/index.html",
        "notes": ["2024年4月1日改定の水間鉄道公式普通旅客運賃表。"],
        "routeIds": ["V4_ROUTE_6F87DA574270ED"],
        "pairs": [
            ("貝塚", "貝塚市役所前", 200),
            ("貝塚", "近義の里", 200),
            ("貝塚", "石才", 250),
            ("貝塚", "清児", 250),
            ("貝塚", "名越", 300),
            ("貝塚", "森", 300),
            ("貝塚", "三ツ松", 330),
            ("貝塚", "三ヶ山口", 330),
            ("貝塚", "水間観音", 330),
            ("貝塚市役所前", "近義の里", 200),
            ("貝塚市役所前", "石才", 250),
            ("貝塚市役所前", "清児", 250),
            ("貝塚市役所前", "名越", 300),
            ("貝塚市役所前", "森", 300),
            ("貝塚市役所前", "三ツ松", 300),
            ("貝塚市役所前", "三ヶ山口", 300),
            ("貝塚市役所前", "水間観音", 330),
            ("近義の里", "石才", 200),
            ("近義の里", "清児", 250),
            ("近義の里", "名越", 250),
            ("近義の里", "森", 300),
            ("近義の里", "三ツ松", 300),
            ("近義の里", "三ヶ山口", 300),
            ("近義の里", "水間観音", 300),
            ("石才", "清児", 200),
            ("石才", "名越", 200),
            ("石才", "森", 250),
            ("石才", "三ツ松", 250),
            ("石才", "三ヶ山口", 300),
            ("石才", "水間観音", 300),
            ("清児", "名越", 200),
            ("清児", "森", 200),
            ("清児", "三ツ松", 250),
            ("清児", "三ヶ山口", 250),
            ("清児", "水間観音", 250),
            ("名越", "森", 200),
            ("名越", "三ツ松", 200),
            ("名越", "三ヶ山口", 250),
            ("名越", "水間観音", 250),
            ("森", "三ツ松", 200),
            ("森", "三ヶ山口", 200),
            ("森", "水間観音", 200),
            ("三ツ松", "三ヶ山口", 200),
            ("三ツ松", "水間観音", 200),
            ("三ヶ山口", "水間観音", 200),
        ],
    },
]


def manual_rows(rows: list[tuple[int, int | None, int]]) -> list[dict[str, Any]]:
    return [{"fromKm": start, "toKm": end, "yen": yen} for start, end, yen in rows]


def station_pair_key(left_name: str, right_name: str) -> str:
    return f"{''.join(left_name.split())}|{''.join(right_name.split())}"


def manual_station_pairs(pairs: list[tuple[str, str, int]]) -> dict[str, dict[str, Any]]:
    return {
        station_pair_key(left_name, right_name): {
            "fromStationName": left_name,
            "toStationName": right_name,
            "yen": yen,
        }
        for left_name, right_name, yen in pairs
    }


def parse_kitakyushu_monorail_pairs(html: str) -> dict[str, dict[str, Any]]:
    station_names: dict[str, str] = {}
    for match in re.finditer(r'<td class="[^"]*\bstation\b[^"]*" data-target="([^"]+)">(.*?)</td>', html, re.S):
        text_match = re.search(r'<span class="text">(.*?)</span>', match.group(2), re.S)
        if text_match:
            station_names[match.group(1)] = "".join(re.sub(r"<[^>]+>", "", text_match.group(1)).split())
    zone_yen = {
        "station-area01": 100,
        "station-area02": 230,
        "station-area03": 290,
        "station-area04": 340,
        "station-area05": 380,
    }
    pairs: dict[str, dict[str, Any]] = {}
    for match in re.finditer(r'<td class="([^"]*adult[^"]*)"', html):
        classes = match.group(1).split()
        zone = next((class_name for class_name in classes if class_name in zone_yen), None)
        if not zone:
            continue
        slugs = [
            class_name for class_name in classes
            if class_name not in {"adult", "child"} and class_name not in zone_yen and class_name in station_names
        ]
        if len(slugs) != 2:
            continue
        left_name = station_names[slugs[0]]
        right_name = station_names[slugs[1]]
        pairs[station_pair_key(left_name, right_name)] = {
            "fromStationName": left_name,
            "toStationName": right_name,
            "yen": zone_yen[zone],
        }
    return pairs


def parse_new_shuttle_pairs(html: str) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for block_match in re.finditer(
        r'<span class="m-box-accordion__head-title">普通片道運賃（きっぷ）</span>(.*?)(?=<span class="m-box-accordion__head-title">IC運賃</span>)',
        html,
        re.S,
    ):
        block = block_match.group(1)
        origin_match = re.search(r'<span class="cred">([^<]+?)（乗車駅）</span>', block)
        if not origin_match:
            continue
        origin_name = "".join(origin_match.group(1).split())
        for row_match in re.finditer(r"<tr>(.*?)</tr>", block, re.S):
            row = row_match.group(1)
            name_match = re.search(r'<th[^>]*>(.*?)</th>', row, re.S)
            adult_match = re.search(r'<td class="tar">([0-9]+)</td>', row)
            if not name_match or not adult_match:
                continue
            dest_text = re.sub(r"<[^>]+>", "", name_match.group(1))
            dest_name = re.sub(r"（乗車駅）", "", "".join(dest_text.split()))
            if not dest_name or dest_name == origin_name:
                continue
            yen = int(adult_match.group(1))
            key = station_pair_key(origin_name, dest_name)
            pairs.setdefault(key, {
                "fromStationName": origin_name,
                "toStationName": dest_name,
                "yen": yen,
            })
    return pairs


def parse_enoden_pairs(html: str) -> dict[str, dict[str, Any]]:
    station_options: dict[int, str] = {}
    for option_match in re.finditer(r'<option value="en(\d+)">([^<]+?)駅</option>', html):
        index = int(option_match.group(1)) - 1
        station_options.setdefault(index, "".join(option_match.group(2).split()))
    table_match = re.search(r"var fareObj = (\[.*?\]);", html, re.S)
    if not table_match:
        return {}
    table = ast.literal_eval(table_match.group(1))
    pairs: dict[str, dict[str, Any]] = {}
    for left_index, row in enumerate(table):
        left_name = station_options.get(left_index)
        if not left_name:
            continue
        for right_index, yen in enumerate(row):
            right_name = station_options.get(right_index)
            if not right_name or right_index <= left_index or not isinstance(yen, int):
                continue
            pairs[station_pair_key(left_name, right_name)] = {
                "fromStationName": left_name,
                "toStationName": right_name,
                "yen": yen,
            }
    return pairs


def clean_sanriku_station_name(raw: str) -> str:
    name = raw.strip()
    name = re.split(r"\s+特定運賃区間|\s+※八木沢は", name)[0]
    for note_start in ["吉里吉里ー", "織笠ー", "八木沢・", "宮古ー", "田老ー", "野田玉川ー"]:
        name = re.split(rf"\s+{re.escape(note_start)}", name)[0]
    name = name.lstrip("※").strip()
    return "".join(name.split())


def parse_sanriku_pairs(lines: list[str]) -> dict[str, dict[str, Any]]:
    rows: list[tuple[str, list[int]]] = []
    station_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^((?:[\d,]+\s+)+)(.+)$", stripped)
        if match:
            fares = list(reversed([parse_money(token) for token in re.findall(r"[\d,]+", match.group(1))]))
            station_name = clean_sanriku_station_name(match.group(2))
            if fares and station_name:
                rows.append((station_name, fares))
                station_count = max(station_count, len(fares) + len(rows))
            continue
        if rows and station_count and len(rows) < station_count and not re.search(r"\d", stripped):
            rows.append((clean_sanriku_station_name(stripped), []))
            if len(rows) >= station_count:
                break

    stations = [station for station, _fares in rows]
    pairs: dict[str, dict[str, Any]] = {}
    for index, (from_station, fares) in enumerate(rows):
        for offset, yen in enumerate(fares, start=1):
            target_index = index + offset
            if target_index >= len(stations):
                continue
            to_station = stations[target_index]
            pairs[station_pair_key(from_station, to_station)] = {
                "fromStationName": from_station,
                "toStationName": to_station,
                "yen": yen,
            }
    return pairs


def parse_kobe_new_transit_pairs(html: str) -> dict[str, dict[str, Any]]:
    table_blocks = re.findall(r'<table class="v2-fee-table[^"]*">(.*?)</table>', html, flags=re.S)
    pairs: dict[str, dict[str, Any]] = {}
    for block in table_blocks[:2]:
        rows = re.findall(r"<tr>(.*?)</tr>", block, flags=re.S)
        station_names: list[str] = []
        row_fares: list[list[int]] = []
        for row in rows:
            th_match = re.search(r"<th[^>]*>(.*?)</th>", row, flags=re.S)
            if not th_match:
                continue
            th_text = re.sub(r"\[[A-Z0-9]+\]", "", th_match.group(1))
            station_name = "".join(re.sub(r"<[^>]+>", "", th_text).split())
            if not station_name:
                continue
            after_header = row[th_match.end():]
            fares = [int(value) for value in re.findall(r'<span class="adu">(\d+)</span>', after_header)]
            station_names.append(station_name)
            row_fares.append(fares)
        for index, from_station in enumerate(station_names):
            for offset, yen in enumerate(row_fares[index], start=1):
                target_index = index + offset
                if target_index >= len(station_names):
                    continue
                to_station = station_names[target_index]
                pairs[station_pair_key(from_station, to_station)] = {
                    "fromStationName": from_station,
                    "toStationName": to_station,
                    "yen": yen,
                }
    return pairs


def clean_station_label(raw: str) -> str:
    raw = re.sub(r'<span[^>]*class="[^"]*\byomi\b[^"]*".*?</span>', "", raw, flags=re.S)
    text = unescape(re.sub(r"<[^>]+>", "", raw))
    text = "".join(text.replace("\xa0", " ").split())
    text = re.sub(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]+", "", text)
    return text


def clean_fare_cell(raw: str) -> str:
    without_bg = re.sub(r'<span[^>]*class="[^"]*\bswl-cell-bg\b[^"]*".*?</span>', "", raw, flags=re.S)
    return "".join(unescape(re.sub(r"<[^>]+>", "", without_bg)).replace("\xa0", " ").split())


def parse_wakayama_dentetsu_pairs(html: str) -> dict[str, dict[str, Any]]:
    block_pattern = re.compile(
        r'<summary[^>]*>.*?<span class="swell-block-accordion__label">(.*?)</span>.*?</summary>'
        r'<div.*?<table.*?>(.*?)</table>',
        re.S,
    )
    pairs: dict[str, dict[str, Any]] = {}
    for _origin_raw, table_html in block_pattern.findall(html):
        parsed_rows: list[tuple[str, str]] = []
        rows = re.findall(r"<tr>(.*?)</tr>", table_html, flags=re.S)
        for row in rows[1:]:
            cells = re.findall(r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", row, flags=re.S)
            if len(cells) < 3:
                continue
            parsed_rows.append((clean_station_label(cells[0]), clean_fare_cell(cells[1])))
        origin_name = next((station for station, adult in parsed_rows if station and not adult.isdigit()), "")
        if not origin_name:
            continue
        for dest_name, adult in parsed_rows:
            if not dest_name or dest_name == origin_name or not adult.isdigit():
                continue
            key = station_pair_key(origin_name, dest_name)
            reverse_key = station_pair_key(dest_name, origin_name)
            if reverse_key in pairs:
                continue
            pairs.setdefault(key, {
                "fromStationName": origin_name,
                "toStationName": dest_name,
                "yen": int(adult),
            })
    return pairs


def add_station_pair(pairs: dict[str, dict[str, Any]], origin_name: str, dest_name: str, yen: int) -> None:
    if not origin_name or not dest_name or origin_name == dest_name:
        return
    key = station_pair_key(origin_name, dest_name)
    reverse_key = station_pair_key(dest_name, origin_name)
    if reverse_key in pairs:
        return
    pairs.setdefault(key, {
        "fromStationName": origin_name,
        "toStationName": dest_name,
        "yen": yen,
    })


def parse_sendai_airport_transit_page(origin_name: str, html: str) -> dict[str, dict[str, Any]]:
    table_match = re.search(r'<table[^>]*class="[^"]*\buntin\b[^"]*"[^>]*>(.*?)</table>', html, flags=re.S)
    if not table_match:
        return {}
    pairs: dict[str, dict[str, Any]] = {}
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.S)
    for row in rows:
        if "kodomo" in row:
            continue
        cells = re.findall(r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", row, flags=re.S)
        if len(cells) < 3:
            continue
        adult = clean_fare_cell(cells[0]).replace(",", "")
        dest_name = clean_station_label(cells[1])
        if adult.isdigit():
            add_station_pair(pairs, origin_name, dest_name, int(adult))
    return pairs


def parse_aonami_line_page(origin_name: str, html: str) -> dict[str, dict[str, Any]]:
    table_match = re.search(r'<div class="price-table">.*?<table>(.*?)</table>', html, flags=re.S)
    if not table_match:
        return {}
    pairs: dict[str, dict[str, Any]] = {}
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), flags=re.S)
    for row in rows:
        cells = re.findall(r"<(?:th|td)[^>]*>(.*?)</(?:th|td)>", row, flags=re.S)
        if len(cells) < 4:
            continue
        dest_name = re.sub(r"\(当駅\)", "", clean_station_label(cells[0]))
        adult = clean_fare_cell(cells[3]).replace(",", "").replace("円", "")
        if adult.isdigit():
            add_station_pair(pairs, origin_name, dest_name, int(adult))
    return pairs


def parse_tama_monorail_page(origin_name: str, html: str) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    current_yen: int | None = None
    rows = re.findall(r"<tr[^>]*class=\"[^\"]*\bprice__row\b[^\"]*\"[^>]*>(.*?)</tr>", html, flags=re.S)
    for row in rows:
        row = re.sub(r"<!--.*?-->", "", row, flags=re.S)
        station_match = re.search(r'<th[^>]*class="[^"]*\bprice__cell--index\b[^"]*"[^>]*>(.*?)</th>', row, flags=re.S)
        if not station_match:
            continue
        dest_name = clean_station_label(station_match.group(1))
        fare_match = re.search(r'<td[^>]*class="[^"]*\bprice__cell--fill--gray\b[^"]*"[^>]*>(.*?)</td>', row, flags=re.S)
        if fare_match:
            fare_text = clean_fare_cell(fare_match.group(1))
            ticket_match = re.search(r"\((\d+)\)", fare_text)
            if ticket_match:
                current_yen = int(ticket_match.group(1))
            elif fare_text.isdigit():
                current_yen = int(fare_text)
            else:
                current_yen = None
        if current_yen is not None:
            add_station_pair(pairs, origin_name, dest_name, current_yen)
    return pairs


def parse_linimo_page(origin_name: str, html: str) -> dict[str, dict[str, Any]]:
    start = html.find("<h2>普通乗車券</h2>")
    if start < 0:
        return {}
    adult_start = html.find("<p class=\"hm_bodytext_l\">大人</p>", start)
    child_start = html.find("<p class=\"hm_bodytext_l\">小児</p>", adult_start)
    if adult_start < 0 or child_start < 0:
        return {}
    adult_block = html[adult_start:child_start]
    pairs: dict[str, dict[str, Any]] = {}
    for row in re.findall(r"<tr>(.*?)</tr>", adult_block, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        if len(cells) < 2:
            continue
        dest_name = clean_station_label(cells[0])
        fare_text = clean_fare_cell(cells[1]).replace(",", "").replace("円", "")
        if fare_text.isdigit():
            add_station_pair(pairs, origin_name, dest_name, int(fare_text))
    return pairs


def parse_ueda_dentetsu_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    try:
        index = lines.index("上田電鉄 ［普通券］ 運賃表") + 2
    except ValueError:
        return pairs
    for origin_index, origin_name in enumerate(station_order[:-1]):
        while index < len(lines) and lines[index] != origin_name:
            if origin_name == "別所温泉" and lines[index:index + 2] == ["別所", "温泉"]:
                break
            index += 1
        if index >= len(lines):
            return pairs
        index += 2 if lines[index:index + 2] == ["別所", "温泉"] else 1
        for dest_name in station_order[origin_index + 1:]:
            if index >= len(lines) or not lines[index].isdigit():
                return pairs
            add_station_pair(pairs, origin_name, dest_name, int(lines[index]))
            index += 1
    return pairs


def parse_chikutetsu_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    fare_rows = [
        line
        for line in lines
        if re.match(r"^(?:\d{3}\s+)+", line)
    ]
    for origin_index, line in enumerate(fare_rows, start=1):
        if origin_index >= len(station_order):
            break
        fares = [int(value) for value in re.findall(r"\d{3}", line)]
        expected_count = origin_index
        if len(fares) < expected_count:
            return pairs
        origin_name = station_order[origin_index]
        for dest_index, yen in enumerate(fares[:expected_count]):
            add_station_pair(pairs, origin_name, station_order[dest_index], yen)
    return pairs


def parse_fukushima_kotsu_iizaka_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    try:
        start_index = lines.index("福島交通飯坂線 普通旅客運賃表")
    except ValueError:
        return pairs
    for origin_index in range(1, len(station_order)):
        line_index = start_index + origin_index * 3
        if line_index >= len(lines):
            return pairs
        fares = [int(value) for value in re.findall(r"\d{3}", lines[line_index])]
        if len(fares) != origin_index:
            return pairs
        origin_name = station_order[origin_index]
        for dest_index, yen in enumerate(fares):
            add_station_pair(pairs, origin_name, station_order[dest_index], yen)
    return pairs


def parse_aichi_loop_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for origin_index, origin_name in enumerate(station_order[1:], start=1):
        line = next((value for value in lines if origin_name in value.split()), "")
        if not line:
            return pairs
        fares = [int(value) for value in re.findall(r"\d{3}", line.split(origin_name, 1)[1])]
        if len(fares) != origin_index:
            return pairs
        for dest_index, yen in enumerate(fares):
            add_station_pair(pairs, origin_name, station_order[dest_index], yen)
    return pairs


def parse_shimabara_railway_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    for origin_index, origin_name in enumerate(station_order[:-1]):
        line = next((value for value in lines if value.startswith(origin_name + " ")), "")
        if not line:
            return pairs
        fares = [int(value) for value in re.findall(r"\d{3,4}", line.split(origin_name, 1)[1])]
        expected_count = len(station_order) - origin_index - 1
        if len(fares) != expected_count:
            return pairs
        for offset, yen in enumerate(fares, start=1):
            add_station_pair(pairs, origin_name, station_order[origin_index + offset], yen)
    return pairs


def parse_ibara_railway_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    add_station_pair(pairs, "総社", "清音", 190)
    fare_rows = [
        line
        for line in lines
        if re.match(r"^[0-9]", line)
    ]
    for origin_index, line in enumerate(fare_rows, start=2):
        if origin_index >= len(station_order):
            break
        values = [
            int(value.replace(",", ""))
            for value in re.findall(r"[0-9]{1,3}(?:,[0-9]{3})*", line)
        ]
        expected_count = origin_index
        if len(values) < expected_count:
            return pairs
        origin_name = station_order[origin_index]
        for dest_index, yen in enumerate(values[:expected_count]):
            add_station_pair(pairs, origin_name, station_order[dest_index], yen)
    return pairs


def parse_kashima_rinkai_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    row_names = station_order[:-3]
    adult_rows = [
        line
        for line in lines
        if line.startswith("大人 ")
    ][:len(row_names)]
    if len(adult_rows) != len(row_names):
        return pairs
    for origin_index, line in enumerate(adult_rows):
        values = [
            int(value.replace(",", ""))
            for value in re.findall(r"[0-9]{1,3}(?:,[0-9]{3})*", line)
        ]
        expected_count = len(station_order) - origin_index - 1
        if len(values) != expected_count:
            return pairs
        origin_name = station_order[origin_index]
        for dest_name, yen in zip(station_order[origin_index + 1:], reversed(values)):
            add_station_pair(pairs, origin_name, dest_name, yen)
    add_station_pair(pairs, "荒野台", "鹿島サッカースタジアム", 230)
    add_station_pair(pairs, "荒野台", "鹿島神宮", 430)
    add_station_pair(pairs, "鹿島サッカースタジアム", "鹿島神宮", 200)
    return pairs


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.lines.append(text)


def fetch_text(url: str, cache_dir: Path) -> tuple[str, list[str]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".html")
    if cache_path.exists():
        html = cache_path.read_text(encoding="utf-8", errors="replace")
    else:
        response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
        response.raise_for_status()
        encoding = response.encoding if response.encoding and response.encoding.lower() != "iso-8859-1" else response.apparent_encoding
        html = response.content.decode(encoding or "utf-8", errors="replace")
        cache_path.write_text(html, encoding="utf-8")
    parser = TextExtractor()
    parser.feed(html)
    return str(cache_path.relative_to(ROOT)), parser.lines


def fetch_raw(url: str, cache_dir: Path) -> tuple[str, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".html")
    if cache_path.exists():
        return str(cache_path.relative_to(ROOT)), cache_path.read_text(encoding="utf-8", errors="replace")
    response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
    response.raise_for_status()
    encoding = response.encoding if response.encoding and response.encoding.lower() != "iso-8859-1" else response.apparent_encoding
    html = response.content.decode(encoding or "utf-8", errors="replace")
    cache_path.write_text(html, encoding="utf-8")
    return str(cache_path.relative_to(ROOT)), html


def fetch_pdf_text(url: str, cache_dir: Path) -> tuple[str, list[str]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".pdf")
    if not cache_path.exists():
        response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
        response.raise_for_status()
        cache_path.write_bytes(response.content)
    completed = subprocess.run(
        ["pdftotext", "-layout", str(cache_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [" ".join(line.split()) for line in completed.stdout.splitlines() if line.strip()]
    return str(cache_path.relative_to(ROOT)), lines


def try_fetch_text(url: str, cache_dir: Path) -> tuple[str | None, list[str], str | None]:
    try:
      cache_path, lines = fetch_text(url, cache_dir)
      return cache_path, lines, None
    except requests.RequestException as error:
      return None, [], str(error)


def parse_money(value: str) -> int:
    return int(re.sub(r"\D+", "", value))


def parse_first_money(value: str) -> int:
    normalized = value.translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
    match = re.search(r"\d[\d,]*", normalized)
    if not match:
        raise ValueError(f"missing money in {value!r}")
    return int(match.group(0).replace(",", ""))


def clean_html_table_cell(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"[ \t\r\f\v]+", " ", value).strip()


def first_html_table_rows_after_marker(html: str, marker: str) -> list[list[str]]:
    start = html.find(marker)
    if start < 0:
        raise ValueError(f"missing marker {marker!r}")
    match = re.search(r"<table\b.*?</table>", html[start:], re.S | re.I)
    if not match:
        raise ValueError(f"missing table after marker {marker!r}")
    table = match.group(0)
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", table, re.S | re.I):
        cells = [
            clean_html_table_cell(cell)
            for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)
        ]
        if cells:
            rows.append(cells)
    return rows


def parse_yamagata_railway_pairs(html: str) -> dict[str, dict[str, Any]]:
    rows = first_html_table_rows_after_marker(html, "普通旅客運賃表")
    header = rows[0]
    station_order = ["赤湯", *header[1:-1]]
    pairs: list[tuple[str, str, int]] = []
    for row_index, row in enumerate(rows[1:]):
        if row_index >= len(station_order) - 1:
            break
        expected_station = station_order[row_index]
        row_station = row[0] if row[0] == expected_station else (row[1] if len(row) > 1 else "")
        if row_station != expected_station:
            raise ValueError(f"unexpected Yamagata row station {row_station!r}, expected {expected_station!r}")
        fare_cells = row[1:-1] if row_index == 0 else row[2:-1]
        expected_count = len(station_order) - row_index - 1
        if len(fare_cells) != expected_count:
            raise ValueError(f"{row_station} fare row has {len(fare_cells)} fares, expected {expected_count}")
        for to_station, fare_cell in zip(station_order[row_index + 1:], fare_cells, strict=True):
            pairs.append((row_station, to_station, parse_first_money(fare_cell)))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Yamagata Railway pair count {len(pairs)} != {expected_pair_count}")
    return manual_station_pairs(pairs)


def parse_moka_railway_pairs(html: str) -> dict[str, dict[str, Any]]:
    rows = first_html_table_rows_after_marker(html, '<div id="unchin-pc"')
    header = rows[0]
    station_order = header[1:]
    pairs: list[tuple[str, str, int]] = []
    for row_index, row in enumerate(rows[1:]):
        if row_index >= len(station_order):
            break
        row_station = row[0]
        if row_station != station_order[row_index]:
            raise ValueError(f"unexpected Moka row station {row_station!r}, expected {station_order[row_index]!r}")
        if len(row) != len(station_order) + 1:
            raise ValueError(f"{row_station} fare row has {len(row)} cells")
        for to_index in range(row_index + 1, len(station_order)):
            pairs.append((row_station, station_order[to_index], parse_first_money(row[to_index + 1])))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Moka Railway pair count {len(pairs)} != {expected_pair_count}")
    return manual_station_pairs(pairs)


def parse_km_range(value: str) -> tuple[int, int | None] | None:
    normalized = value.replace(",", "")
    match = re.search(r"(\d+)-(\d+)", normalized)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)キロまで", normalized)
    if match:
        return 1, int(match.group(1))
    match = re.search(r"(\d+)キロ以上", normalized)
    if match:
        return int(match.group(1)), None
    return None


def marker_index(lines: list[str], marker: str) -> int:
    for index, line in enumerate(lines):
        if marker in line:
            return index
    return -1


def parse_adjacent_range_fare_rows(lines: list[str], marker: str, max_rows: int = 80) -> list[dict[str, Any]]:
    start = marker_index(lines, marker)
    if start < 0:
        return []
    rows: list[dict[str, Any]] = []
    index = start + 1
    while index < len(lines) - 1 and len(rows) < max_rows:
        km_range = parse_km_range(lines[index])
        if km_range and re.search(r"円$", lines[index + 1]):
            rows.append({"fromKm": km_range[0], "toKm": km_range[1], "yen": parse_money(lines[index + 1])})
            index += 2
            continue
        if rows and (lines[index].startswith("PR") or "運賃表" in lines[index] or "料金表" in lines[index]):
            break
        index += 1
    return rows


def parse_limited_express_rows(lines: list[str], marker: str, max_rows: int = 16) -> list[dict[str, Any]]:
    start = marker_index(lines, marker)
    if start < 0:
        return []
    rows: list[dict[str, Any]] = []
    index = start + 1
    while index < len(lines) - 2 and len(rows) < max_rows:
        km_range = parse_km_range(lines[index])
        if km_range and re.search(r"円$", lines[index + 1]) and re.search(r"円$", lines[index + 2]):
            rows.append({
                "fromKm": km_range[0],
                "toKm": km_range[1],
                "reservedYen": parse_money(lines[index + 1]),
                "unreservedYen": parse_money(lines[index + 2]),
            })
            index += 3
            continue
        if rows and (lines[index].startswith("PR") or "料金表" in lines[index]):
            break
        index += 1
    return rows


def build_rules(cache_dir: Path) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    ordinary_tables: dict[str, Any] = {}
    station_pair_tables: dict[str, Any] = {}
    for source in JR_FARE_SOURCES:
        cache_path, lines = fetch_text(source["url"], cache_dir)
        source_record = {
            "key": source["key"],
            "url": source["url"],
            "cachePath": cache_path,
            "kind": "ordinary_fare_table",
            "operatorIds": source["operatorIds"],
        }
        sources.append(source_record)
        parsed_tables = {}
        for table in source["tables"]:
            rows = parse_adjacent_range_fare_rows(lines, table["marker"])
            if rows:
                parsed_tables[table["key"]] = {
                    "marker": table["marker"],
                    "rows": rows,
                }
        ordinary_tables[source["key"]] = {
            "operatorIds": source["operatorIds"],
            "sourceKey": source["key"],
            "tables": parsed_tables,
        }

    limited_cache_path, limited_lines = fetch_text(LIMITED_EXPRESS_SOURCE["url"], cache_dir)
    sources.append({
        "key": LIMITED_EXPRESS_SOURCE["key"],
        "url": LIMITED_EXPRESS_SOURCE["url"],
        "cachePath": limited_cache_path,
        "kind": "limited_express_surcharge_table",
    })
    limited_tables = {}
    for table in LIMITED_EXPRESS_SOURCE["tables"]:
        rows = parse_limited_express_rows(limited_lines, table["marker"])
        if rows:
            limited_tables[table["key"]] = {
                "marker": table["marker"],
                "rows": rows,
            }

    for reference in OFFICIAL_REFERENCE_SOURCES:
        cache_path, _lines, error = try_fetch_text(reference["url"], cache_dir)
        record = {
            **reference,
            "kind": "official_reference",
        }
        if cache_path:
            record["cachePath"] = cache_path
        if error:
            record["fetchError"] = error
        sources.append(record)

    for table in MANUAL_OPERATOR_FARE_TABLES:
        cache_path, _lines, error = try_fetch_text(table["url"], cache_dir)
        source_record = {
            "key": table["key"],
            "url": table["url"],
            "kind": "ordinary_fare_table",
            "operatorIds": table["operatorIds"],
            "operatorName": table["operatorName"],
            "extraction": "manual_from_official_source",
        }
        if cache_path:
            source_record["cachePath"] = cache_path
        if error:
            source_record["fetchError"] = error
        sources.append(source_record)
        ordinary_tables[table["key"]] = {
            "operatorIds": table["operatorIds"],
            **({"routeIds": table["routeIds"]} if table.get("routeIds") else {}),
            "sourceKey": table["key"],
            "operatorName": table["operatorName"],
            "notes": table.get("notes") or [],
            "tables": {
                "main": {
                    "marker": "adult ordinary fare table",
                    "rows": manual_rows(table["rows"]),
                },
            },
        }

    for table in MANUAL_STATION_PAIR_FARE_TABLES:
        cache_path, _lines, error = try_fetch_text(table["url"], cache_dir)
        source_record = {
            "key": table["key"],
            "url": table["url"],
            "kind": "station_pair_fare_table",
            "operatorIds": table["operatorIds"],
            "operatorName": table["operatorName"],
            "extraction": "manual_from_official_source",
        }
        if cache_path:
            source_record["cachePath"] = cache_path
        if error:
            source_record["fetchError"] = error
        sources.append(source_record)
        station_pair_tables[table["key"]] = {
            "operatorIds": table["operatorIds"],
            **({"routeIds": table["routeIds"]} if table.get("routeIds") else {}),
            "sourceKey": table["key"],
            "operatorName": table["operatorName"],
            "notes": table.get("notes") or [],
            "pairs": manual_station_pairs(table["pairs"]),
        }

    kitakyushu = KITAKYUSHU_MONORAIL_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(kitakyushu["url"], cache_dir)
    kitakyushu_pairs = parse_kitakyushu_monorail_pairs(html)
    sources.append({
        "key": kitakyushu["key"],
        "url": kitakyushu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": kitakyushu["operatorIds"],
        "operatorName": kitakyushu["operatorName"],
        "extraction": "parsed_station_pair_classes_from_official_html",
        "pairCount": len(kitakyushu_pairs),
    })
    station_pair_tables[kitakyushu["key"]] = {
        "operatorIds": kitakyushu["operatorIds"],
        "routeIds": kitakyushu["routeIds"],
        "sourceKey": kitakyushu["key"],
        "operatorName": kitakyushu["operatorName"],
        "notes": kitakyushu["notes"],
        "pairs": kitakyushu_pairs,
    }

    new_shuttle = NEW_SHUTTLE_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(new_shuttle["url"], cache_dir)
    new_shuttle_pairs = parse_new_shuttle_pairs(html)
    sources.append({
        "key": new_shuttle["key"],
        "url": new_shuttle["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": new_shuttle["operatorIds"],
        "operatorName": new_shuttle["operatorName"],
        "extraction": "parsed_station_pair_rows_from_official_html",
        "pairCount": len(new_shuttle_pairs),
    })
    station_pair_tables[new_shuttle["key"]] = {
        "operatorIds": new_shuttle["operatorIds"],
        "routeIds": new_shuttle["routeIds"],
        "sourceKey": new_shuttle["key"],
        "operatorName": new_shuttle["operatorName"],
        "notes": new_shuttle["notes"],
        "pairs": new_shuttle_pairs,
    }

    enoden = ENODEN_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(enoden["url"], cache_dir)
    enoden_pairs = parse_enoden_pairs(html)
    sources.append({
        "key": enoden["key"],
        "url": enoden["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": enoden["operatorIds"],
        "operatorName": enoden["operatorName"],
        "extraction": "parsed_js_fare_matrix_from_official_html",
        "pairCount": len(enoden_pairs),
    })
    station_pair_tables[enoden["key"]] = {
        "operatorIds": enoden["operatorIds"],
        "routeIds": enoden["routeIds"],
        "sourceKey": enoden["key"],
        "operatorName": enoden["operatorName"],
        "notes": enoden["notes"],
        "pairs": enoden_pairs,
    }

    sanriku = SANRIKU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(sanriku["url"], cache_dir)
    sanriku_pairs = parse_sanriku_pairs(lines)
    sources.append({
        "key": sanriku["key"],
        "url": sanriku["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": sanriku["operatorIds"],
        "operatorName": sanriku["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_pdf",
        "pairCount": len(sanriku_pairs),
    })
    station_pair_tables[sanriku["key"]] = {
        "operatorIds": sanriku["operatorIds"],
        "routeIds": sanriku["routeIds"],
        "sourceKey": sanriku["key"],
        "operatorName": sanriku["operatorName"],
        "notes": sanriku["notes"],
        "pairs": sanriku_pairs,
    }

    kobe_new_transit = KOBE_NEW_TRANSIT_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(kobe_new_transit["url"], cache_dir)
    kobe_new_transit_pairs = parse_kobe_new_transit_pairs(html)
    sources.append({
        "key": kobe_new_transit["key"],
        "url": kobe_new_transit["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": kobe_new_transit["operatorIds"],
        "operatorName": kobe_new_transit["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_html",
        "pairCount": len(kobe_new_transit_pairs),
    })
    station_pair_tables[kobe_new_transit["key"]] = {
        "operatorIds": kobe_new_transit["operatorIds"],
        "routeIds": kobe_new_transit["routeIds"],
        "sourceKey": kobe_new_transit["key"],
        "operatorName": kobe_new_transit["operatorName"],
        "notes": kobe_new_transit["notes"],
        "pairs": kobe_new_transit_pairs,
    }

    wakayama_dentetsu = WAKAYAMA_DENTETSU_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(wakayama_dentetsu["url"], cache_dir)
    wakayama_dentetsu_pairs = parse_wakayama_dentetsu_pairs(html)
    sources.append({
        "key": wakayama_dentetsu["key"],
        "url": wakayama_dentetsu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": wakayama_dentetsu["operatorIds"],
        "operatorName": wakayama_dentetsu["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_html",
        "pairCount": len(wakayama_dentetsu_pairs),
    })
    station_pair_tables[wakayama_dentetsu["key"]] = {
        "operatorIds": wakayama_dentetsu["operatorIds"],
        "routeIds": wakayama_dentetsu["routeIds"],
        "sourceKey": wakayama_dentetsu["key"],
        "operatorName": wakayama_dentetsu["operatorName"],
        "notes": wakayama_dentetsu["notes"],
        "pairs": wakayama_dentetsu_pairs,
    }

    sendai_airport = SENDAI_AIRPORT_TRANSIT_STATION_PAIR_SOURCE
    sendai_airport_pairs: dict[str, dict[str, Any]] = {}
    sendai_airport_cache_paths: list[str] = []
    for origin_name, url in sendai_airport["pages"]:
        cache_path, html = fetch_raw(url, cache_dir)
        sendai_airport_cache_paths.append(cache_path)
        for pair in parse_sendai_airport_transit_page(origin_name, html).values():
            add_station_pair(
                sendai_airport_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    sources.append({
        "key": sendai_airport["key"],
        "urls": [url for _origin_name, url in sendai_airport["pages"]],
        "cachePaths": sendai_airport_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": sendai_airport["operatorIds"],
        "operatorName": sendai_airport["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pages",
        "pairCount": len(sendai_airport_pairs),
    })
    station_pair_tables[sendai_airport["key"]] = {
        "operatorIds": sendai_airport["operatorIds"],
        "routeIds": sendai_airport["routeIds"],
        "sourceKey": sendai_airport["key"],
        "operatorName": sendai_airport["operatorName"],
        "notes": sendai_airport["notes"],
        "pairs": sendai_airport_pairs,
    }

    aonami_line = AONAMI_LINE_STATION_PAIR_SOURCE
    aonami_line_pairs: dict[str, dict[str, Any]] = {}
    aonami_line_cache_paths: list[str] = []
    for origin_name, url in aonami_line["pages"]:
        cache_path, html = fetch_raw(url, cache_dir)
        aonami_line_cache_paths.append(cache_path)
        for pair in parse_aonami_line_page(origin_name, html).values():
            add_station_pair(
                aonami_line_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    sources.append({
        "key": aonami_line["key"],
        "urls": [url for _origin_name, url in aonami_line["pages"]],
        "cachePaths": aonami_line_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": aonami_line["operatorIds"],
        "operatorName": aonami_line["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pages",
        "pairCount": len(aonami_line_pairs),
    })
    station_pair_tables[aonami_line["key"]] = {
        "operatorIds": aonami_line["operatorIds"],
        "routeIds": aonami_line["routeIds"],
        "sourceKey": aonami_line["key"],
        "operatorName": aonami_line["operatorName"],
        "notes": aonami_line["notes"],
        "pairs": aonami_line_pairs,
    }

    tama_monorail = TAMA_MONORAIL_STATION_PAIR_SOURCE
    tama_monorail_pairs: dict[str, dict[str, Any]] = {}
    tama_monorail_cache_paths: list[str] = []
    for origin_name, url in tama_monorail["pages"]:
        cache_path, html = fetch_raw(url, cache_dir)
        tama_monorail_cache_paths.append(cache_path)
        for pair in parse_tama_monorail_page(origin_name, html).values():
            add_station_pair(
                tama_monorail_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    sources.append({
        "key": tama_monorail["key"],
        "urls": [url for _origin_name, url in tama_monorail["pages"]],
        "cachePaths": tama_monorail_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": tama_monorail["operatorIds"],
        "operatorName": tama_monorail["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pages",
        "pairCount": len(tama_monorail_pairs),
    })
    station_pair_tables[tama_monorail["key"]] = {
        "operatorIds": tama_monorail["operatorIds"],
        "routeIds": tama_monorail["routeIds"],
        "sourceKey": tama_monorail["key"],
        "operatorName": tama_monorail["operatorName"],
        "notes": tama_monorail["notes"],
        "pairs": tama_monorail_pairs,
    }

    linimo = LINIMO_STATION_PAIR_SOURCE
    linimo_pairs: dict[str, dict[str, Any]] = {}
    linimo_cache_paths: list[str] = []
    for origin_name, url in linimo["pages"]:
        cache_path, html = fetch_raw(url, cache_dir)
        linimo_cache_paths.append(cache_path)
        for pair in parse_linimo_page(origin_name, html).values():
            add_station_pair(
                linimo_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    sources.append({
        "key": linimo["key"],
        "urls": [url for _origin_name, url in linimo["pages"]],
        "cachePaths": linimo_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": linimo["operatorIds"],
        "operatorName": linimo["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pages",
        "pairCount": len(linimo_pairs),
    })
    station_pair_tables[linimo["key"]] = {
        "operatorIds": linimo["operatorIds"],
        "routeIds": linimo["routeIds"],
        "sourceKey": linimo["key"],
        "operatorName": linimo["operatorName"],
        "notes": linimo["notes"],
        "pairs": linimo_pairs,
    }

    ueda_dentetsu = UEDA_DENTETSU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_text(ueda_dentetsu["url"], cache_dir)
    ueda_dentetsu_pairs = parse_ueda_dentetsu_pairs(
        lines,
        ueda_dentetsu["stationOrder"],
    )
    sources.append({
        "key": ueda_dentetsu["key"],
        "url": ueda_dentetsu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": ueda_dentetsu["operatorIds"],
        "operatorName": ueda_dentetsu["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_html",
        "pairCount": len(ueda_dentetsu_pairs),
    })
    station_pair_tables[ueda_dentetsu["key"]] = {
        "operatorIds": ueda_dentetsu["operatorIds"],
        "routeIds": ueda_dentetsu["routeIds"],
        "sourceKey": ueda_dentetsu["key"],
        "operatorName": ueda_dentetsu["operatorName"],
        "notes": ueda_dentetsu["notes"],
        "pairs": ueda_dentetsu_pairs,
    }

    chikutetsu = CHIKUTETSU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(chikutetsu["url"], cache_dir)
    chikutetsu_pairs = parse_chikutetsu_pairs(
        lines,
        chikutetsu["stationOrder"],
    )
    sources.append({
        "key": chikutetsu["key"],
        "url": chikutetsu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": chikutetsu["operatorIds"],
        "operatorName": chikutetsu["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(chikutetsu_pairs),
    })
    station_pair_tables[chikutetsu["key"]] = {
        "operatorIds": chikutetsu["operatorIds"],
        "routeIds": chikutetsu["routeIds"],
        "sourceKey": chikutetsu["key"],
        "operatorName": chikutetsu["operatorName"],
        "notes": chikutetsu["notes"],
        "pairs": chikutetsu_pairs,
    }

    fukushima_kotsu = FUKUSHIMA_KOTSU_IIZAKA_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(fukushima_kotsu["url"], cache_dir)
    fukushima_kotsu_pairs = parse_fukushima_kotsu_iizaka_pairs(
        lines,
        fukushima_kotsu["stationOrder"],
    )
    sources.append({
        "key": fukushima_kotsu["key"],
        "url": fukushima_kotsu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": fukushima_kotsu["operatorIds"],
        "operatorName": fukushima_kotsu["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(fukushima_kotsu_pairs),
    })
    station_pair_tables[fukushima_kotsu["key"]] = {
        "operatorIds": fukushima_kotsu["operatorIds"],
        "routeIds": fukushima_kotsu["routeIds"],
        "sourceKey": fukushima_kotsu["key"],
        "operatorName": fukushima_kotsu["operatorName"],
        "notes": fukushima_kotsu["notes"],
        "pairs": fukushima_kotsu_pairs,
    }

    aichi_loop = AICHI_LOOP_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(aichi_loop["url"], cache_dir)
    aichi_loop_pairs = parse_aichi_loop_pairs(lines, aichi_loop["stationOrder"])
    sources.append({
        "key": aichi_loop["key"],
        "url": aichi_loop["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": aichi_loop["operatorIds"],
        "operatorName": aichi_loop["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(aichi_loop_pairs),
    })
    station_pair_tables[aichi_loop["key"]] = {
        "operatorIds": aichi_loop["operatorIds"],
        "routeIds": aichi_loop["routeIds"],
        "sourceKey": aichi_loop["key"],
        "operatorName": aichi_loop["operatorName"],
        "notes": aichi_loop["notes"],
        "pairs": aichi_loop_pairs,
    }

    shimabara_railway = SHIMABARA_RAILWAY_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(shimabara_railway["url"], cache_dir)
    shimabara_railway_pairs = parse_shimabara_railway_pairs(
        lines,
        shimabara_railway["stationOrder"],
    )
    sources.append({
        "key": shimabara_railway["key"],
        "url": shimabara_railway["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": shimabara_railway["operatorIds"],
        "operatorName": shimabara_railway["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(shimabara_railway_pairs),
    })
    station_pair_tables[shimabara_railway["key"]] = {
        "operatorIds": shimabara_railway["operatorIds"],
        "routeIds": shimabara_railway["routeIds"],
        "sourceKey": shimabara_railway["key"],
        "operatorName": shimabara_railway["operatorName"],
        "notes": shimabara_railway["notes"],
        "pairs": shimabara_railway_pairs,
    }

    ibara_railway = IBARA_RAILWAY_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(ibara_railway["url"], cache_dir)
    ibara_railway_pairs = parse_ibara_railway_pairs(
        lines,
        ibara_railway["stationOrder"],
    )
    sources.append({
        "key": ibara_railway["key"],
        "url": ibara_railway["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": ibara_railway["operatorIds"],
        "operatorName": ibara_railway["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(ibara_railway_pairs),
    })
    station_pair_tables[ibara_railway["key"]] = {
        "operatorIds": ibara_railway["operatorIds"],
        "routeIds": ibara_railway["routeIds"],
        "sourceKey": ibara_railway["key"],
        "operatorName": ibara_railway["operatorName"],
        "notes": ibara_railway["notes"],
        "pairs": ibara_railway_pairs,
    }

    kashima_rinkai = KASHIMA_RINKAI_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(kashima_rinkai["url"], cache_dir)
    kashima_rinkai_pairs = parse_kashima_rinkai_pairs(
        lines,
        kashima_rinkai["stationOrder"],
    )
    sources.append({
        "key": kashima_rinkai["key"],
        "url": kashima_rinkai["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": kashima_rinkai["operatorIds"],
        "operatorName": kashima_rinkai["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(kashima_rinkai_pairs),
    })
    station_pair_tables[kashima_rinkai["key"]] = {
        "operatorIds": kashima_rinkai["operatorIds"],
        "routeIds": kashima_rinkai["routeIds"],
        "sourceKey": kashima_rinkai["key"],
        "operatorName": kashima_rinkai["operatorName"],
        "notes": kashima_rinkai["notes"],
        "pairs": kashima_rinkai_pairs,
    }

    yamagata_railway = YAMAGATA_RAILWAY_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(yamagata_railway["url"], cache_dir)
    yamagata_railway_pairs = parse_yamagata_railway_pairs(html)
    sources.append({
        "key": yamagata_railway["key"],
        "url": yamagata_railway["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": yamagata_railway["operatorIds"],
        "operatorName": yamagata_railway["operatorName"],
        "extraction": "parsed_station_pair_table_from_official_html",
        "pairCount": len(yamagata_railway_pairs),
    })
    station_pair_tables[yamagata_railway["key"]] = {
        "operatorIds": yamagata_railway["operatorIds"],
        "routeIds": yamagata_railway["routeIds"],
        "sourceKey": yamagata_railway["key"],
        "operatorName": yamagata_railway["operatorName"],
        "notes": yamagata_railway["notes"],
        "pairs": yamagata_railway_pairs,
    }

    moka_railway = MOKA_RAILWAY_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(moka_railway["url"], cache_dir)
    moka_railway_pairs = parse_moka_railway_pairs(html)
    sources.append({
        "key": moka_railway["key"],
        "url": moka_railway["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": moka_railway["operatorIds"],
        "operatorName": moka_railway["operatorName"],
        "extraction": "parsed_station_pair_table_from_official_html",
        "pairCount": len(moka_railway_pairs),
    })
    station_pair_tables[moka_railway["key"]] = {
        "operatorIds": moka_railway["operatorIds"],
        "routeIds": moka_railway["routeIds"],
        "sourceKey": moka_railway["key"],
        "operatorName": moka_railway["operatorName"],
        "notes": moka_railway["notes"],
        "pairs": moka_railway_pairs,
    }

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "modelVersion": "v4_collected_fare_rules_2026_05",
        "currency": "JPY",
        "sources": sources,
        "ordinaryFareTables": ordinary_tables,
        "stationPairFareTables": station_pair_tables,
        "limitedExpressSurchargeTables": limited_tables,
        "coverageNotes": [
            "JR ordinary fare tables and conventional limited express surcharge tables are collected from published fare-rule pages.",
            "The game fare resolver uses these tables for JR distance-band legs and marks fare as unknown where no collected operator table exists.",
            "Limited express fare is represented as base fare plus surcharge; reserved ordinary-car normal-season surcharge is used as the default.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    payload = build_rules(args.cache_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.relative_to(ROOT)),
        "ordinaryTableCount": len(payload["ordinaryFareTables"]),
        "stationPairTableCount": len(payload["stationPairFareTables"]),
        "limitedExpressTableCount": len(payload["limitedExpressSurchargeTables"]),
        "sourceCount": len(payload["sources"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
