#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from datetime import datetime, timezone
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
        "key": "sotetsu",
        "operatorIds": ["sotetsu"],
        "operatorName": "相模鉄道",
        "url": "https://www.sotetsu.co.jp/media/2019/trans/train/search/pdf/kiro_fares.pdf",
        "notes": ["キロ別旅客運賃表・大人普通運賃・きっぷ10円単位。いずみ野線加算運賃は未適用。"],
        "rows": [(1, 3, 150), (4, 7, 180), (8, 11, 200), (12, 15, 230),
                 (16, 19, 260), (20, 23, 280), (24, 26, 310)],
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
]

MANUAL_STATION_PAIR_FARE_TABLES: list[dict[str, Any]] = [
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
    response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
    response.raise_for_status()
    cache_path.write_text(response.text, encoding=response.encoding or "utf-8")
    parser = TextExtractor()
    parser.feed(response.text)
    return str(cache_path.relative_to(ROOT)), parser.lines


def fetch_raw(url: str, cache_dir: Path) -> tuple[str, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".html")
    response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    cache_path.write_text(response.text, encoding=response.encoding)
    return str(cache_path.relative_to(ROOT)), response.text


def fetch_pdf_text(url: str, cache_dir: Path) -> tuple[str, list[str]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_") + ".pdf")
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
