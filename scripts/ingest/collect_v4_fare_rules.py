#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
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
        "key": "sotetsu",
        "operatorIds": ["sotetsu"],
        "operatorName": "相模鉄道",
        "url": "https://www.sotetsu.co.jp/media/2019/trans/train/search/pdf/kiro_fares.pdf",
        "notes": ["キロ別旅客運賃表・大人普通運賃・きっぷ10円単位。いずみ野線加算運賃は未適用。"],
        "rows": [(1, 3, 150), (4, 7, 180), (8, 11, 200), (12, 15, 230),
                 (16, 19, 260), (20, 23, 280), (24, 26, 310)],
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
]

MANUAL_STATION_PAIR_FARE_TABLES: list[dict[str, Any]] = [
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
