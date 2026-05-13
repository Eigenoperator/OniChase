#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "data" / "v4_fare_rules.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "v4_fare_source_cache"


def cache_stem_for_url(url: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", url).strip("_")
    if len(stem) > 160:
        stem = f"{stem[:120]}_{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}"
    return stem

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

YORO_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "yoro_railway_station_pairs_202502",
    "operatorIds": ["養老鉄道"],
    "operatorName": "養老鉄道",
    "url": "https://www.yororailway.co.jp/wp-content/uploads/2025/02/fare-data01.pdf",
    "routeIds": ["V4_ROUTE_E7786B27777EE4"],
    "stationOrder": [
        "桑名",
        "播磨",
        "下深谷",
        "下野代",
        "多度",
        "美濃松山",
        "石津",
        "美濃山崎",
        "駒野",
        "美濃津屋",
        "養老",
        "美濃高田",
        "烏江",
        "大外羽",
        "友江",
        "美濃青柳",
        "西大垣",
        "大垣",
        "室",
        "北大垣",
        "東赤坂",
        "広神戸",
        "北神戸",
        "池野",
        "北池野",
        "美濃本郷",
        "揖斐",
    ],
    "notes": [
        "養老鉄道公式の全体普通運賃表PDFから、上段の大人普通運賃だけを抽出。下段の小児運賃、通勤・通学定期、回数券、1日フリーきっぷは別体系のため未収録。",
    ],
}

MATSUURA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "matsuura_railway_station_pairs_202410",
    "operatorIds": ["松浦鉄道"],
    "operatorName": "松浦鉄道",
    "url": "https://matutetu.com/relays/download/787/2103/326//?file=%2Ffiles%2Flibs%2F4890%2F202408251723586779.pdf&file_name=%E6%99%AE%E9%80%9A%E6%97%85%E5%AE%A2%E9%81%8B%E8%B3%83%E8%A1%A8%E3%80%96%E4%BB%A4%E5%92%8C6%E5%B9%B410%E6%9C%881%E6%97%A5%E6%94%B9%E5%AE%9A%E3%80%97",
    "routeIds": ["V4_ROUTE_188DAD9E0512B4"],
    "stationOrder": [
        "有田",
        "三代橋",
        "黒川",
        "蔵宿",
        "西有田",
        "大木",
        "山谷",
        "夫婦石",
        "金武",
        "川東",
        "伊万里",
        "東山代",
        "里",
        "楠久",
        "鳴石",
        "久原",
        "波瀬",
        "浦ノ崎",
        "福島口",
        "今福",
        "鷹島口",
        "前浜",
        "調川",
        "松浦",
        "松浦発電所前",
        "御厨",
        "西木場",
        "東田平",
        "中田平",
        "たびら平戸口",
        "西田平",
        "すえたちばな",
        "江迎鹿町",
        "高岩",
        "いのつき",
        "潜竜ヶ滝",
        "吉井",
        "神田",
        "清峰高校前",
        "佐々",
        "小浦",
        "真申",
        "棚方",
        "相浦",
        "大学",
        "上相浦",
        "本山",
        "中里",
        "皆瀬",
        "野中",
        "左石",
        "泉福寺",
        "山の田",
        "北佐世保",
        "中佐世保",
        "佐世保中央",
        "佐世保",
    ],
    "notes": [
        "松浦鉄道公式の2024年10月1日改定・駅間普通旅客運賃表（実施）PDFから大人普通運賃の全駅間三角表を抽出。PDFは3ページに分割され、後半駅は前半30駅への表と後半駅同士の表を結合している。",
        "小児運賃、定期運賃、団体運賃、企画乗車券は別体系のため未収録。",
    ],
}

NAGARAGAWA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "nagaragawa_railway_station_pairs_202203",
    "operatorIds": ["長良川鉄道"],
    "operatorName": "長良川鉄道",
    "url": "http://www.nagatetsu.co.jp/wp/wp-content/uploads/2022/04/20220312RegularFare.pdf",
    "routeIds": ["V4_ROUTE_EB781F5E159E91"],
    "stationOrder": [
        "美濃太田",
        "前平公園",
        "加茂野",
        "富加",
        "関富岡",
        "関口",
        "せきてらす前",
        "関",
        "関市役所前",
        "関下有知",
        "松森",
        "美濃市",
        "梅山",
        "湯の洞温泉口",
        "洲原",
        "母野",
        "木尾",
        "八坂",
        "みなみ子宝温泉",
        "大矢",
        "福野",
        "美並苅安",
        "赤池",
        "深戸",
        "相生",
        "郡上八幡",
        "自然園前",
        "山田",
        "徳永",
        "郡上大和",
        "万場",
        "上万場",
        "大中",
        "大島",
        "美濃白鳥",
        "白鳥高原",
        "白山長滝",
        "北濃",
    ],
    "notes": [
        "長良川鉄道公式の普通旅客運賃表PDF（2022年3月12日掲載、令和元年10月1日改正）から大人普通運賃の全駅間三角表を抽出。",
        "小児運賃、定期運賃、回数券、企画乗車券、観光列車料金は別体系のため未収録。",
    ],
}

ECHIZEN_KATSUYAMA_STATION_PAIR_SOURCE = {
    "key": "echizen_katsuyama_station_pairs_202403",
    "operatorIds": ["えちぜん鉄道"],
    "operatorName": "えちぜん鉄道",
    "url": "https://www.echizen-tetudo.co.jp/.assets/%E6%97%85%E5%AE%A2%E9%81%8B%E8%B3%83%E8%A1%A8.pdf",
    "routeIds": ["V4_ROUTE_B926BEF5FF2C42"],
    "stationOrder": [
        "福井",
        "新福井",
        "福井口",
        "越前開発",
        "越前新保",
        "追分口",
        "東藤島",
        "越前島橋",
        "観音町",
        "松岡",
        "志比堺",
        "永平寺口",
        "下志比",
        "光明寺",
        "轟",
        "越前野中",
        "山王",
        "越前竹原",
        "小舟渡",
        "保田",
        "発坂",
        "比島",
        "勝山",
    ],
    "notes": [
        "えちぜん鉄道公式の2024年3月16日改正・旅客運賃表PDFから、勝山永平寺線の大人普通運賃三角表だけを抽出。ゲーム側の三国芦原線 route は福井鉄道直通区間を含むため、この表では勝山永平寺線 route だけを覆う。",
        "回数券、通勤定期、通学定期、障害者割引、福井鉄道連絡運賃は別体系のため未収録。",
    ],
}

TOSAKURO_NAKAMURA_SUKUMO_STATION_PAIR_SOURCE = {
    "key": "tosakuro_nakamura_sukumo_station_pairs",
    "operatorIds": ["土佐くろしお鉄道"],
    "operatorName": "土佐くろしお鉄道",
    "url": "https://www.tosakuro.com/_files/ugd/310f5f_37eea061f96741e38687f6acba2d20f7.pdf",
    "routeIds": ["V4_ROUTE_3D26D21D635155", "V4_ROUTE_CFD933ACA2790A"],
    "stationOrder": [
        "窪川",
        "若井",
        "荷稲",
        "伊与喜",
        "土佐佐賀",
        "佐賀公園",
        "土佐白浜",
        "有井川",
        "土佐上川口",
        "海の王迎",
        "浮鞭",
        "土佐入野",
        "西大方",
        "古津賀",
        "中村",
        "具同",
        "国見",
        "有岡",
        "工業団地",
        "平田",
        "東宿毛",
        "宿毛",
    ],
    "notes": [
        "土佐くろしお鉄道公式の中村・宿毛線運賃表PDFから大人普通運賃の駅間三角表を抽出。PDF右側には自由席特急料金表も併載されているため、普通運賃行の先頭側の駅間運賃だけを使用する。",
        "自由席特急料金、こども運賃、定期運賃、割引乗車券は別体系のため未収録。ごめん・なはり線はゲーム route にJR高知側の尾巴が混在しているため、この表では覆わない。",
    ],
}

ICHIBATA_STATION_PAIR_SOURCE = {
    "key": "ichibata_station_pairs_202503",
    "operatorIds": ["一畑電車"],
    "operatorName": "一畑電車",
    "url": "https://railway.ichibata.co.jp/wp-content/media/fare20250301.pdf",
    "routeIds": ["V4_ROUTE_9783546D7EAF3F", "V4_ROUTE_4B83A1B9C42AEF"],
    "stationOrder": [
        "電鉄出雲市",
        "出雲科学館パークタウン前",
        "大津町",
        "武志",
        "川跡",
        "大寺",
        "美談",
        "旅伏",
        "雲州平田",
        "布崎",
        "湖遊館新駅",
        "園",
        "一畑口",
        "伊野灘",
        "津ノ森",
        "高ノ宮",
        "松江フォーゲルパーク",
        "秋鹿町",
        "長江",
        "朝日ヶ丘",
        "松江イングリッシュガーデン前",
        "松江しんじ湖温泉",
        "高浜",
        "遥堪",
        "浜山公園北口",
        "出雲大社前",
    ],
    "samplePairs": {
        "電鉄出雲市|出雲科学館パークタウン前": 190,
        "電鉄出雲市|松江しんじ湖温泉": 770,
        "電鉄出雲市|出雲大社前": 550,
        "川跡|出雲大社前": 400,
        "高浜|遥堪": 190,
        "松江しんじ湖温泉|出雲大社前": 900,
        "遥堪|出雲大社前": 190,
    },
    "notes": [
        "一畑電車公式の2025年3月1日改定・普通旅客運賃表PDFから、全社駅間表の上段（大人普通運賃）だけを抽出。PDFの下段小人運賃、定期、回数券、割引乗車券は別体系のため未収録。",
        "ゲーム側表記に合わせ、公式PDFの「遙堪」は「遥堪」に正規化している。北松江線・大社線は同一事業者内で駅間表が一体のため、会社全体の station-pair 表として収録する。",
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

KEIHAN_ISHIYAMA_SAKAMOTO_STATION_PAIR_SOURCE = {
    "key": "keihan_ishiyama_sakamoto_station_pairs_202510",
    "operatorIds": ["京阪電気鉄道"],
    "operatorName": "京阪電気鉄道",
    "routeIds": ["V4_ROUTE_62F34CE15D1FDD"],
    "pages": [
        ("石山寺", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/600.pdf"),
        ("唐橋前", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/601.pdf"),
        ("京阪石山", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/602.pdf"),
        ("粟津", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/603.pdf"),
        ("瓦ヶ浜", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/604.pdf"),
        ("中ノ庄", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/605.pdf"),
        ("膳所本町", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/606.pdf"),
        ("錦", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/607.pdf"),
        ("京阪膳所", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/608.pdf"),
        ("石場", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/609.pdf"),
        ("島ノ関", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/610.pdf"),
        ("びわ湖浜大津", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/611.pdf"),
        ("三井寺", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/612.pdf"),
        ("大津市役所前", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/613.pdf"),
        ("京阪大津京", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/614.pdf"),
        ("近江神宮前", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/615.pdf"),
        ("南滋賀", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/616.pdf"),
        ("滋賀里", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/617.pdf"),
        ("穴太", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/618.pdf"),
        ("松ノ馬場", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/619.pdf"),
        ("坂本比叡山口", "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/620.pdf"),
    ],
    "stationOrder": [
        "石山寺", "唐橋前", "京阪石山", "粟津", "瓦ヶ浜", "中ノ庄", "膳所本町", "錦",
        "京阪膳所", "石場", "島ノ関", "びわ湖浜大津", "三井寺", "大津市役所前",
        "京阪大津京", "近江神宮前", "南滋賀", "滋賀里", "穴太", "松ノ馬場", "坂本比叡山口",
    ],
    "notes": [
        "京阪公式の各駅普通運賃・定期券運賃PDF（2025年10月1日改定）から、石山坂本線内の大人普通運賃だけを抽出。京津線、京都市営地下鉄連絡、定期券、小児運賃は別体系のため未収録。",
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

JOSHIN_DENTETSU_STATION_PAIR_SOURCE = {
    "key": "joshin_dentetsu_station_pairs_2026",
    "operatorIds": ["上信電鉄"],
    "operatorName": "上信電鉄",
    "routeIds": ["V4_ROUTE_F2FF376BAD3742"],
    "stationOrder": [
        "高崎",
        "南高崎",
        "佐野のわたし",
        "根小屋",
        "高崎商科大学前",
        "山名",
        "西山名",
        "馬庭",
        "吉井",
        "西吉井",
        "上州新屋",
        "上州福島",
        "東富岡",
        "上州富岡",
        "西富岡",
        "上州七日市",
        "上州一ノ宮",
        "神農原",
        "南蛇井",
        "千平",
        "下仁田",
    ],
    "pages": [
        ("高崎", "https://www.joshin-dentetsu.co.jp/station/12/"),
        ("南高崎", "https://www.joshin-dentetsu.co.jp/station/13/"),
        ("佐野のわたし", "https://www.joshin-dentetsu.co.jp/station/14/"),
        ("根小屋", "https://www.joshin-dentetsu.co.jp/station/15/"),
        ("高崎商科大学前", "https://www.joshin-dentetsu.co.jp/station/17/"),
        ("山名", "https://www.joshin-dentetsu.co.jp/station/18/"),
        ("西山名", "https://www.joshin-dentetsu.co.jp/station/19/"),
        ("馬庭", "https://www.joshin-dentetsu.co.jp/station/20/"),
        ("吉井", "https://www.joshin-dentetsu.co.jp/station/21/"),
        ("西吉井", "https://www.joshin-dentetsu.co.jp/station/22/"),
        ("上州新屋", "https://www.joshin-dentetsu.co.jp/station/23/"),
        ("上州福島", "https://www.joshin-dentetsu.co.jp/station/24/"),
        ("東富岡", "https://www.joshin-dentetsu.co.jp/station/25/"),
        ("上州富岡", "https://www.joshin-dentetsu.co.jp/station/26/"),
        ("西富岡", "https://www.joshin-dentetsu.co.jp/station/27/"),
        ("上州七日市", "https://www.joshin-dentetsu.co.jp/station/28/"),
        ("上州一ノ宮", "https://www.joshin-dentetsu.co.jp/station/29/"),
        ("神農原", "https://www.joshin-dentetsu.co.jp/station/30/"),
        ("南蛇井", "https://www.joshin-dentetsu.co.jp/station/31/"),
        ("千平", "https://www.joshin-dentetsu.co.jp/station/32/"),
        ("下仁田", "https://www.joshin-dentetsu.co.jp/station/33/"),
    ],
    "notes": [
        "上信電鉄公式の各駅ページに掲載された片道運賃表から、大人普通運賃を駅間表として抽出。",
    ],
}

JOMO_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "jomo_railway_station_pairs_201910",
    "operatorIds": ["上毛電気鉄道"],
    "operatorName": "上毛電気鉄道",
    "url": "https://jomorailway.com/fare_nomal.html",
    "routeIds": ["V4_ROUTE_63569A128DCFA4"],
    "stationOrder": [
        "中央前橋",
        "城東",
        "三俣",
        "片貝",
        "上泉",
        "赤坂",
        "心臓血管センター",
        "江木",
        "大胡",
        "樋越",
        "北原",
        "新屋",
        "粕川",
        "膳",
        "新里",
        "新川",
        "東新川",
        "赤城",
        "桐生球場前",
        "天王宿",
        "富士山下",
        "丸山下",
        "西桐生",
    ],
    "notes": [
        "上毛電気鉄道公式の駅間普通旅客運賃表（令和元年10月1日から）から、大人普通運賃を駅間表として抽出。",
    ],
}

CHICHIBU_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "chichibu_railway_station_pairs_202410",
    "operatorIds": ["秩父鉄道"],
    "operatorName": "秩父鉄道",
    "url": "https://www.chichibu-railway.co.jp/train/wp-content/uploads/sites/2/2024/09/kakueki_20241001.pdf",
    "routeIds": ["V4_ROUTE_47E4369685B9DF"],
    "stationOrder": [
        "羽生",
        "西羽生",
        "新郷",
        "武州荒木",
        "東行田",
        "行田市",
        "持田",
        "ソシオ流通センター",
        "熊谷",
        "上熊谷",
        "石原",
        "ひろせ野鳥の森",
        "大麻生",
        "明戸",
        "武川",
        "永田",
        "ふかや花園",
        "小前田",
        "桜沢",
        "寄居",
        "波久礼",
        "樋口",
        "野上",
        "長瀞",
        "上長瀞",
        "親鼻",
        "皆野",
        "和銅黒谷",
        "大野原",
        "秩父",
        "御花畑",
        "影森",
        "浦山口",
        "武州中川",
        "武州日野",
        "白久",
        "三峰口",
    ],
    "notes": [
        "秩父鉄道公式の各駅定期・普通運賃表PDF（2024年10月1日以降）から、大人普通運賃を駅間表として抽出。",
    ],
}

TENHAMA_STATION_PAIR_SOURCE = {
    "key": "tenhama_station_pairs_202410",
    "operatorIds": ["天竜浜名湖鉄道"],
    "operatorName": "天竜浜名湖鉄道",
    "url": "https://www.tenhama.co.jp/wp-content/uploads/078e045baf8688aca2ed7b1d2e5893ce.pdf",
    "routeIds": ["V4_ROUTE_096F9D1B898AF5"],
    "stationOrder": [
        "掛川",
        "掛川市役所前",
        "西掛川",
        "桜木",
        "いこいの広場",
        "細谷",
        "原谷",
        "原田",
        "戸綿",
        "遠州森",
        "森町病院前",
        "円田",
        "遠江一宮",
        "敷地",
        "豊岡",
        "上野部",
        "天竜二俣",
        "二俣本町",
        "西鹿島",
        "岩水寺",
        "宮口",
        "フルーツパーク",
        "都田",
        "常葉大学前",
        "金指",
        "岡地",
        "気賀",
        "西気賀",
        "寸座",
        "浜名湖佐久米",
        "東都筑",
        "都筑",
        "三ヶ日",
        "奥浜名湖",
        "尾奈",
        "知波田",
        "大森",
        "アスモ前",
        "新所原",
    ],
    "notes": [
        "天竜浜名湖鉄道公式の全体運賃表（2024年10月1日運賃改定）から、大人普通旅客運賃の駅間三角表を抽出。",
    ],
}

NAGANO_DENTETSU_STATION_PAIR_SOURCE = {
    "key": "nagano_dentetsu_station_pairs_202512",
    "operatorIds": ["長野電鉄"],
    "operatorName": "長野電鉄",
    "url": "https://www.nagaden-net.co.jp/hubfs/unchin_20251201.pdf?hsLang=ja",
    "routeIds": ["V4_ROUTE_51D54564F0D68F"],
    "stationOrder": [
        "長野",
        "市役所前",
        "権堂",
        "善光寺下",
        "本郷",
        "桐原",
        "信濃吉田",
        "朝陽",
        "附属中学前",
        "柳原",
        "村山",
        "日野",
        "須坂",
        "北須坂",
        "小布施",
        "都住",
        "桜沢",
        "延徳",
        "信州中野",
        "中野松川",
        "信濃竹原",
        "夜間瀬",
        "上条",
        "湯田中",
    ],
    "notes": [
        "長野電鉄公式の全線運賃表PDF（令和7年12月1日改定）から、大人普通旅客運賃の駅間三角表を抽出。",
        "特急料金（一律大人100円）は普通運賃とは別体系のため、この表には含めない。",
    ],
}

KANTETSU_STATION_PAIR_SOURCE = {
    "key": "kantetsu_station_pairs_202410",
    "operatorIds": ["関東鉄道"],
    "operatorName": "関東鉄道",
    "routeIds": ["V4_ROUTE_B53EC1588BC817", "V4_ROUTE_522E1C1515745E"],
    "baseUrl": "https://www.kantetsu.co.jp/train/files_fare/",
    "stationOrder": [
        "取手",
        "西取手",
        "寺原",
        "新取手",
        "ゆめみ野",
        "稲戸井",
        "戸頭",
        "南守谷",
        "守谷",
        "新守谷",
        "小絹",
        "水海道",
        "北水海道",
        "中妻",
        "三妻",
        "南石下",
        "石下",
        "玉村",
        "宗道",
        "下妻",
        "大宝",
        "騰波ノ江",
        "黒子",
        "大田郷",
        "下館",
        "佐貫",
        "入地",
        "竜ヶ崎",
    ],
    "pages": [
        "1_toride.pdf",
        "2_nishitoride.pdf",
        "3_terahara.pdf",
        "4_shintoride.pdf",
        "5_yumemino.pdf",
        "6_inatoi.pdf",
        "7_togashira.pdf",
        "8_minamimoriya.pdf",
        "9_moriya.pdf",
        "10_shinmoriya.pdf",
        "11_kokinu.pdf",
        "12_mitsukaido.pdf",
        "13_kitamitsukaido.pdf",
        "14_nakatsuma.pdf",
        "15_mitsuma.pdf",
        "16_minamiishige.pdf",
        "17_ishige.pdf",
        "18_tamamura.pdf",
        "19_sodo.pdf",
        "20_shimotsuma.pdf",
        "21_daiho.pdf",
        "22_tobanoe.pdf",
        "23_kurogo.pdf",
        "24_otago.pdf",
        "25_shimodate.pdf",
        "28_ryugasaki.pdf",
    ],
    "notes": [
        "関東鉄道公式の各駅運賃表PDF（2024年10月1日改正）から、常総線・竜ヶ崎線の大人普通運賃を駅間表として抽出。IC運賃・定期運賃は別体系のため未収録。",
    ],
}

SANGI_RAILWAY_STATION_PAIR_SOURCES = [
    {
        "key": "sangi_railway_sangi_line_station_pairs_201910",
        "operatorIds": ["三岐鉄道"],
        "operatorName": "三岐鉄道",
        "url": "https://sangirail.co.jp/files/20191001sangi-unchin(1).pdf",
        "routeIds": ["V4_ROUTE_13E9D86DF2B2BD"],
        "stationOrder": [
            "近鉄富田",
            "大矢知",
            "平津",
            "暁学園前",
            "山城",
            "保々",
            "北勢中央公園口",
            "梅戸井",
            "大安",
            "三里",
            "丹生川",
            "伊勢治田",
            "東藤原",
            "西野尻",
            "西藤原",
        ],
        "rowLabels": {
            "北勢中央公園口": "公園口",
        },
        "notes": [
            "三岐鉄道公式の三岐線普通運賃表PDF（2019年10月1日改定）から、大人普通運賃の駅間三角表を抽出。定期券欄は除外。",
        ],
    },
    {
        "key": "sangi_railway_hokusei_line_station_pairs_201910",
        "operatorIds": ["三岐鉄道"],
        "operatorName": "三岐鉄道",
        "url": "https://sangirail.co.jp/files/20191001hokusei-unchin.pdf",
        "routeIds": ["V4_ROUTE_171C260C28EB92"],
        "stationOrder": [
            "西桑名",
            "馬道",
            "西別所",
            "蓮花寺",
            "在良",
            "星川",
            "七和",
            "穴太",
            "東員",
            "大泉",
            "楚原",
            "麻生田",
            "阿下喜",
        ],
        "notes": [
            "三岐鉄道公式の北勢線普通運賃表PDF（2019年10月1日改定）から、大人普通運賃の駅間三角表を抽出。定期券欄は除外。",
        ],
    },
]

AKITA_NAIRIKU_STATION_PAIR_SOURCE = {
    "key": "akita_nairiku_station_pairs_202003",
    "operatorIds": ["秋田内陸縦貫鉄道"],
    "operatorName": "秋田内陸縦貫鉄道",
    "url": "https://www.akita-nairiku.com/fare/pdf/nairiku_fare20200314.pdf",
    "routeIds": ["V4_ROUTE_27982D8F6724D8"],
    "stationOrder": [
        "鷹巣",
        "西鷹巣",
        "縄文小ヶ田",
        "大野台",
        "合川",
        "上杉",
        "米内沢",
        "桂瀬",
        "阿仁前田温泉",
        "前田南",
        "小渕",
        "阿仁合",
        "荒瀬",
        "萱草",
        "笑内",
        "岩野目",
        "比立内",
        "奥阿仁",
        "阿仁マタギ",
        "戸沢",
        "上桧木内",
        "左通",
        "羽後中里",
        "松葉",
        "羽後長戸呂",
        "八津",
        "西明寺",
        "羽後太田",
        "角館",
    ],
    "rowLabels": {
        "縄文小ヶ田": "小ケ田",
        "阿仁前田温泉": "田温泉",
        "阿仁マタギ": "マタギ",
        "戸沢": "戸 沢",
        "上桧木内": "木 内",
        "左通": "左 通",
        "羽後中里": "中 里",
        "羽後長戸呂": "長戸呂",
        "八津": "八 津",
        "羽後太田": "太 田",
    },
    "notes": [
        "秋田内陸縦貫鉄道公式の駅間普通運賃表PDFから、大人普通運賃の駅間三角表を抽出。PDF下部の急行料金表は普通運賃ではないため除外。",
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

NISHIKIGAWA_RAILWAY_STATION_PAIR_SOURCE = {
    "key": "nishikigawa_railway_station_pairs",
    "operatorIds": ["錦川鉄道"],
    "operatorName": "錦川鉄道",
    "url": "https://nishikigawa.com/fare-table/",
    "routeIds": ["V4_ROUTE_D3F7FC3026DBAF"],
    "stationOrder": [
        "岩国",
        "西岩国",
        "川西",
        "清流新岩国",
        "守内かさ神",
        "南河内",
        "行波",
        "北河内",
        "椋野",
        "南桑",
        "根笠",
        "河山",
        "柳瀬",
        "錦町",
    ],
    "notes": [
        "錦川鉄道公式の運賃表ページから大人普通運賃を抽出。公式ページの注記どおり川西-岩国間はJR岩徳線だが、錦川鉄道公式表が岩国・西岩国を含む全駅相互運賃として掲載しているため、ゲーム側の錦川清流線 route 全体を station-pair 表で覆う。",
        "小児運賃、定期運賃、各種割引、企画券は別体系のため未収録。",
    ],
}

WATARASE_KEIKOKU_STATION_PAIR_SOURCE = {
    "key": "watarase_keikoku_station_pairs",
    "operatorIds": ["わたらせ渓谷鐵道"],
    "operatorName": "わたらせ渓谷鐵道",
    "url": "https://www.watetsu.com/rail-info/fare.php",
    "routeIds": ["V4_ROUTE_F010FCAB5431F6"],
    "stationOrder": [
        "桐生",
        "下新田",
        "相老",
        "運動公園",
        "大間々",
        "上神梅",
        "本宿",
        "水沼",
        "花輪",
        "中野",
        "小中",
        "神戸",
        "沢入",
        "原向",
        "通洞",
        "足尾",
        "間藤",
    ],
    "notes": [
        "わたらせ渓谷鐵道公式の運賃表ページに掲載された普通旅客運賃表から、各出発駅別の大人普通運賃だけを抽出。小児運賃、定期運賃、一日フリーきっぷ、トロッコ整理券・料金、団体割引は別体系のため未収録。",
    ],
}

# Real adult ordinary fare tables from official operator fare pages/PDFs.
# Values use the ticket / 10-yen unit fare where operators publish both IC and ticket fares,
# because gameplay fares are displayed as a simple yen total and should avoid 1-yen IC rounding details.
MANUAL_OPERATOR_FARE_TABLES = [
    {
        "key": "aoimori_railway_202604",
        "operatorIds": ["青い森鉄道"],
        "operatorName": "青い森鉄道",
        "url": "https://aoimorirailway.com/wp/wp-content/uploads/2014/02/5a93c1badfcb4aa9f3d80b9c129fffc8.pdf",
        "notes": [
            "青い森鉄道公式の大人片道普通旅客運賃表PDFから、営業キロ別の大人普通運賃を収録。小児運賃、定期運賃、割引乗車券、企画乗車券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_6A7139C8218F8C"],
        "rows": [
            (1, 3, 230),
            (4, 6, 300),
            (7, 10, 320),
            (11, 15, 390),
            (16, 20, 540),
            (21, 25, 680),
            (26, 30, 810),
            (31, 35, 950),
            (36, 40, 1090),
            (41, 45, 1230),
            (46, 50, 1370),
            (51, 60, 1590),
            (61, 70, 1860),
            (71, 80, 2140),
            (81, 90, 2430),
            (91, 100, 2700),
            (101, 120, 3160),
            (121, 122, 3700),
        ],
    },
    {
        "key": "hisatsu_orange_railway_202603",
        "operatorIds": ["肥薩おれんじ鉄道"],
        "operatorName": "肥薩おれんじ鉄道",
        "url": "https://www.hs-orange.com/common/UploadFileOutput.ashx?c_id=3&flid=3561&id=929&sub_id=5",
        "notes": [
            "肥薩おれんじ鉄道公式の2026年3月14日施行・旅客営業規則［別表3］大人普通旅客運賃から、対キロ区間制の大人普通運賃を収録。小児運賃、定期運賃、回数券、団体運賃、特殊割引、連絡運輸は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_F1520AA0FD7BC2"],
        "rows": [
            (1, 3, 230),
            (4, 6, 290),
            (7, 9, 340),
            (10, 12, 400),
            (13, 15, 430),
            (16, 20, 590),
            (21, 25, 700),
            (26, 30, 840),
            (31, 35, 980),
            (36, 40, 1120),
            (41, 45, 1270),
            (46, 50, 1410),
            (51, 55, 1550),
            (56, 60, 1580),
            (61, 65, 1790),
            (66, 70, 1830),
            (71, 80, 2040),
            (81, 90, 2240),
            (91, 100, 2450),
            (101, 110, 2640),
            (111, 117, 2810),
        ],
    },
    {
        "key": "hokuso_railway_202504",
        "operatorIds": ["北総鉄道"],
        "operatorName": "北総鉄道",
        "url": "https://www.hokuso-railway.co.jp/docs/railway/passenger_sales.pdf",
        "notes": [
            "北総鉄道公式の2025年4月1日旅客営業規則第50条に掲載された大人片道普通旅客運賃を収録。IC 1円単位運賃、京成・都営地下鉄・京急等との連絡運賃、乗継割引、定期、回数券、団体、特殊割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_E304DA5E373162"],
        "rows": [
            (1, 3, 190),
            (4, 5, 280),
            (6, 7, 330),
            (8, 9, 380),
            (10, 11, 430),
            (12, 14, 480),
            (15, 17, 550),
            (18, 20, 620),
            (21, 23, 670),
            (24, 26, 720),
            (27, 29, 770),
            (30, 33, 820),
        ],
    },
    {
        "key": "izuhakone_railway_202403",
        "operatorIds": ["伊豆箱根鉄道"],
        "operatorName": "伊豆箱根鉄道",
        "url": "https://www.izuhakone.co.jp/sunzudaiyu/zunzu_sub_nav/schedule/p010102_d/fil/railway__20240316.pdf",
        "notes": [
            "伊豆箱根鉄道公式の2024年3月16日改定普通旅客運賃表。駿豆線・大雄山線共通の営業キロ分段による大人普通運賃で、公式駅間表と同じ分段を収録。",
        ],
        "routeIds": ["V4_ROUTE_50912B7A0CB22D", "V4_ROUTE_FA934902412828"],
        "rows": [
            (1, 3, 160),
            (4, 4, 170),
            (5, 5, 190),
            (6, 6, 210),
            (7, 7, 240),
            (8, 8, 270),
            (9, 10, 310),
            (11, 12, 360),
            (13, 14, 400),
            (15, 16, 440),
            (17, 18, 490),
            (19, 20, 550),
        ],
    },
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
        "key": "keisei_matsudo_line_202603",
        "operatorIds": ["新京成電鉄"],
        "operatorName": "京成電鉄松戸線",
        "url": "https://new-www.keisei.co.jp/keisei/tetudou/goriyo/pdf/keisei_260314.pdf",
        "notes": [
            "京成電鉄公式の2026年3月14日旅客営業規則第77条第6項から、松戸線各駅相互発着の大人片道普通旅客運賃だけを収録。ゲーム側 routeId は旧新京成線のままだが、2025年4月1日の京成電鉄への合併後は京成松戸線として同条項が適用される。",
            "京成本線・成田スカイアクセス線・北総線との乗継/連絡運賃、IC運賃、小児運賃、定期、空港加算、バリアフリー料金、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_446917FE264A8D"],
        "rows": [
            (1, 5, 170),
            (6, 9, 190),
            (10, 13, 210),
            (14, 17, 230),
            (18, 22, 260),
            (23, 27, 280),
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
        "key": "kumagawa_railway_ordinary_2026",
        "operatorIds": ["くま川鉄道"],
        "operatorName": "くま川鉄道",
        "url": "https://kumagawa-rail.com/time-fare/",
        "notes": [
            "くま川鉄道公式の運賃の計算方法に掲載された対キロ区間制・大人普通旅客運賃。2026年時点では人吉温泉-肥後西村が代替バス運行だが、公式運賃は列車・代替バスを含む同社区間として扱われている。小児、定期、団体、割引、1日乗車券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_4420B6F9908A9F"],
        "rows": [
            (1, 3, 190),
            (4, 5, 220),
            (6, 7, 250),
            (8, 9, 290),
            (10, 11, 340),
            (12, 13, 380),
            (14, 15, 430),
            (16, 17, 480),
            (18, 19, 530),
            (20, 21, 590),
            (22, 23, 650),
            (24, 25, 700),
        ],
    },
    {
        "key": "noto_railway_ordinary_201910",
        "operatorIds": ["のと鉄道"],
        "operatorName": "のと鉄道",
        "url": "https://nototetsu.jp/wp-content/uploads/2022/12/2019.10kaisei-ninka.pdf",
        "notes": [
            "のと鉄道公式の2019年10月1日改定認可PDFに掲載された大人普通運賃の対キロ区間制。七尾-和倉温泉間の特定運賃190円は station-pair 特例として別表に収録。",
        ],
        "routeIds": ["V4_ROUTE_5F3470AE16E598"],
        "rows": [
            (1, 4, 210),
            (5, 8, 290),
            (9, 10, 370),
            (11, 12, 380),
            (13, 15, 430),
            (16, 16, 460),
            (17, 20, 530),
            (21, 24, 610),
            (25, 28, 690),
            (29, 32, 780),
            (33, 34, 850),
        ],
    },
    {
        "key": "kotoden_ordinary_202305",
        "operatorIds": ["高松琴平電気鉄道"],
        "operatorName": "高松琴平電気鉄道",
        "url": "https://www.kotoden.co.jp/publichtm/kotoden/fare/image/kiro.pdf",
        "notes": [
            "高松琴平電気鉄道公式の2023年5月20日改定・普通旅客運賃表に掲載された大人普通運賃の営業キロ区間制。PDFに明記された特定区間は station-pair 特例として別表に収録。小児、通勤・通学定期、企画券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_A45E51F5787C3A", "V4_ROUTE_23B25267C45ED3", "V4_ROUTE_D647E5F3ACC083"],
        "rows": [
            (1, 4, 200),
            (5, 6, 270),
            (7, 8, 360),
            (9, 10, 400),
            (11, 12, 430),
            (13, 14, 470),
            (15, 16, 510),
            (17, 18, 550),
            (19, 20, 590),
            (21, 22, 630),
            (23, 24, 650),
            (25, 26, 670),
            (27, 28, 690),
            (29, 31, 710),
            (32, 34, 730),
            (35, 37, 750),
            (38, 40, 770),
            (41, 43, 790),
            (44, 46, 810),
        ],
    },
    {
        "key": "konan_railway_ordinary_201910",
        "operatorIds": ["弘南鉄道"],
        "operatorName": "弘南鉄道",
        "url": "https://konantetsudo.jp/fare/01_futsu_katamichi_201910.pdf",
        "notes": [
            "弘南鉄道公式の2019年10月1日改定・弘南線/大鰐線普通旅客運賃表に掲載された大人普通運賃。PDFは上段にキロ程、下段に大人運賃を示すため、営業キロを1km単位に切り上げた区間制として収録。小児運賃、定期券、回数券、団体割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_035A41A4C6F538", "V4_ROUTE_662E6CC073EE1E"],
        "rows": [
            (1, 2, 210),
            (3, 3, 270),
            (4, 4, 300),
            (5, 5, 330),
            (6, 6, 350),
            (7, 7, 370),
            (8, 8, 380),
            (9, 9, 390),
            (10, 10, 400),
            (11, 11, 410),
            (12, 12, 420),
            (13, 13, 430),
            (14, 14, 440),
            (15, 15, 450),
            (16, 16, 460),
            (17, 17, 470),
        ],
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
        "notes": [
            "2025年4月1日改定の南海線及び高野線対キロ区間制。南海・泉北合併により旧泉北高速線にも南海電鉄の運賃表を適用。空港線加算運賃と鋼索線は別表で収録するためこの対キロ表では覆わない。",
        ],
        "routeIds": [
            "V4_ROUTE_F60089BDD83AB8",
            "V4_ROUTE_B6CB90953DCB01",
            "V4_ROUTE_606F2D70D0B351",
            "V4_ROUTE_180A8AC3E9B282",
            "V4_ROUTE_CB287DAA293B22",
            "V4_ROUTE_3B2B50773C0B7A",
            "V4_ROUTE_43CB80819A14B6",
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
        "key": "iyotetsu_suburban_railway_202604",
        "operatorIds": ["伊予鉄道"],
        "operatorName": "伊予鉄道",
        "url": "https://www.iyotetsu.co.jp/sp/topics/26/0401_rail.pdf",
        "notes": [
            "伊予鉄道公式の2026年4月1日改定・鉄道事業/軌道事業参考資料に掲載された鉄道線の大人普通旅客運賃。ゲーム内の単純表示は現金決済相当とし、キャッシュレス20円割引、定期券、1Dayチケット、市内電車均一運賃は別体系として扱う。",
        ],
        "routeIds": [
            "V4_ROUTE_C92EC5B30F1884",
            "V4_ROUTE_1F3EF7559F4A46",
            "V4_ROUTE_7FFA6625483820",
        ],
        "rows": [
            (1, 3, 250),
            (4, 4, 300),
            (5, 5, 320),
            (6, 6, 380),
            (7, 7, 400),
            (8, 9, 460),
            (10, 11, 520),
            (12, 13, 580),
            (14, 15, 640),
            (16, 17, 700),
            (18, 19, 750),
            (20, 21, 800),
            (22, 23, 820),
            (24, 25, 820),
        ],
    },
    {
        "key": "ohmi_railway_201910_current",
        "operatorIds": ["近江鉄道"],
        "operatorName": "近江鉄道",
        "url": "https://wwwtb.mlit.go.jp/kinki/content/000332962.pdf",
        "notes": [
            "国土交通省近畿運輸局の近江鉄道旅客運賃上限設定認可申請資料に掲載された普通旅客運賃（大人）。同資料の参考欄で現行運賃は普通旅客運賃160円から1,050円で変わらないとされているため、2026年時点のゲーム内普通運賃分段として収録。",
        ],
        "routeIds": [
            "V4_ROUTE_B6AF6112315CFE",
            "V4_ROUTE_E62AF762866424",
            "V4_ROUTE_60D1E17DCF42DB",
        ],
        "rows": [
            (1, 2, 160),
            (3, 3, 180),
            (4, 5, 250),
            (6, 7, 310),
            (8, 9, 390),
            (10, 11, 460),
            (12, 13, 530),
            (14, 15, 590),
            (16, 17, 650),
            (18, 19, 700),
            (20, 21, 760),
            (22, 24, 800),
            (25, 27, 850),
            (28, 30, 890),
            (31, 33, 930),
            (34, 36, 960),
            (37, 39, 990),
            (40, 42, 1010),
            (43, 45, 1030),
            (46, 48, 1050),
        ],
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


def station_pair_upper_triangle_rows(
    station_order: list[str],
    fare_rows: list[tuple[str, list[int]]],
) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for row_station, fares in fare_rows:
        row_index = station_order.index(row_station)
        expected = len(station_order) - row_index - 1
        if len(fares) != expected:
            raise ValueError(f"{row_station} fare row has {len(fares)} fares, expected {expected}")
        for next_station, yen in zip(station_order[row_index + 1:], fares, strict=True):
            pairs.append((row_station, next_station, yen))
    return pairs


def station_pair_flat_rows(station_order: list[str], yen: int) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for index, station in enumerate(station_order):
        for next_station in station_order[index + 1:]:
            pairs.append((station, next_station, yen))
    return pairs


def station_pair_cross_rows(
    left_station_order: list[str],
    fare_rows: list[tuple[str, list[int]]],
) -> list[tuple[str, str, int]]:
    pairs: list[tuple[str, str, int]] = []
    for row_station, fares in fare_rows:
        if len(fares) != len(left_station_order):
            raise ValueError(f"{row_station} cross fare row has {len(fares)} fares, expected {len(left_station_order)}")
        for left_station, yen in zip(left_station_order, fares, strict=True):
            pairs.append((left_station, row_station, yen))
    return pairs


MANUAL_STATION_PAIR_FARE_TABLES: list[dict[str, Any]] = [
    {
        "key": "kyoto_tango_railway_station_pairs_201910",
        "operatorIds": ["willertrains"],
        "operatorName": "WILLER TRAINS",
        "url": "https://trains.willer.co.jp/ticket/faretable/pdf/faretable201910.pdf",
        "notes": [
            "京都丹後鉄道公式の普通旅客運賃表PDFから、宮舞線・宮豊線・宮福線の大人普通運賃だけを収録。宮津線側、西舞鶴-豊岡の宮舞/宮豊線内、宮村-福知山の宮福線内、宮津を介した両線間の普通運賃を同じ公式表から転記している。",
            "小児運賃、特急料金、特別車両料金、観光列車整理券、企画乗車券、回数券、定期、団体・割引運賃、JR連絡運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_69F491596F64E6", "V4_ROUTE_CB37B94EC12D1E"],
        "pairs": station_pair_triangle_rows(
            [
                "西舞鶴",
                "四所",
                "東雲",
                "丹後神崎",
                "丹後由良",
                "栗田",
                "宮津",
                "天橋立",
                "岩滝口",
                "与謝野",
                "京丹後大宮",
                "峰山",
                "網野",
                "夕日ヶ浦木津温泉",
                "小天橋",
                "かぶと山",
                "久美浜",
                "コウノトリの郷",
                "豊岡",
            ],
            [
                ("四所", [200]),
                ("東雲", [250, 200]),
                ("丹後神崎", [350, 250, 200]),
                ("丹後由良", [350, 250, 200, 150]),
                ("栗田", [450, 350, 300, 250, 200]),
                ("宮津", [600, 450, 400, 300, 300, 200]),
                ("天橋立", [650, 500, 450, 400, 350, 250, 200]),
                ("岩滝口", [700, 650, 500, 450, 450, 350, 250, 200]),
                ("与謝野", [800, 700, 600, 500, 500, 400, 300, 250, 150]),
                ("京丹後大宮", [1000, 850, 800, 650, 650, 500, 400, 350, 300, 250]),
                ("峰山", [1100, 1000, 950, 800, 800, 650, 500, 450, 400, 350, 200]),
                ("網野", [1200, 1150, 1100, 1000, 950, 800, 700, 600, 500, 450, 350, 250]),
                ("夕日ヶ浦木津温泉", [1300, 1200, 1150, 1100, 1100, 950, 850, 700, 650, 600, 450, 350, 200]),
                ("小天橋", [1450, 1300, 1200, 1150, 1150, 1100, 950, 850, 800, 700, 500, 450, 300, 200]),
                ("かぶと山", [1450, 1400, 1300, 1200, 1200, 1100, 1000, 950, 850, 800, 600, 500, 350, 250, 200]),
                ("久美浜", [1500, 1450, 1400, 1300, 1200, 1150, 1100, 1000, 950, 850, 650, 500, 400, 300, 200, 150]),
                ("コウノトリの郷", [1500, 1500, 1500, 1450, 1450, 1300, 1200, 1150, 1100, 1000, 850, 700, 600, 450, 350, 300, 250]),
                ("豊岡", [1500, 1500, 1500, 1500, 1450, 1400, 1300, 1200, 1150, 1100, 950, 800, 650, 500, 400, 350, 300, 150]),
            ],
        )
        + station_pair_upper_triangle_rows(
            [
                "宮村",
                "喜多",
                "辛皮",
                "大江山口内宮",
                "二俣",
                "大江高校前",
                "大江",
                "公庄",
                "下天津",
                "牧",
                "荒河かしの木台",
                "福知山市民病院口",
                "福知山",
            ],
            [
                ("宮村", [150, 250, 300, 350, 400, 400, 450, 500, 500, 600, 650, 650]),
                ("喜多", [200, 300, 300, 350, 350, 400, 450, 500, 600, 600, 650]),
                ("辛皮", [200, 200, 250, 250, 300, 350, 400, 450, 450, 500]),
                ("大江山口内宮", [150, 200, 200, 250, 300, 350, 350, 400, 400]),
                ("二俣", [150, 150, 200, 250, 300, 350, 350, 400]),
                ("大江高校前", [150, 200, 200, 250, 300, 300, 350]),
                ("大江", [150, 200, 250, 300, 300, 350]),
                ("公庄", [150, 200, 250, 250, 300]),
                ("下天津", [150, 200, 250, 250]),
                ("牧", [150, 200, 200]),
                ("荒河かしの木台", [150, 150]),
                ("福知山市民病院口", [150]),
            ],
        )
        + station_pair_cross_rows(
            [
                "西舞鶴",
                "四所",
                "東雲",
                "丹後神崎",
                "丹後由良",
                "栗田",
                "宮津",
                "天橋立",
                "岩滝口",
                "与謝野",
                "京丹後大宮",
                "峰山",
                "網野",
                "夕日ヶ浦木津温泉",
                "小天橋",
                "かぶと山",
                "久美浜",
                "コウノトリの郷",
                "豊岡",
            ],
            [
                ("宮村", [600, 450, 400, 350, 300, 200, 150, 200, 300, 350, 450, 600, 700, 850, 1000, 1100, 1100, 1200, 1300]),
                ("喜多", [650, 500, 450, 400, 350, 250, 200, 250, 300, 350, 500, 600, 800, 950, 1000, 1100, 1150, 1300, 1300]),
                ("辛皮", [800, 650, 600, 500, 450, 350, 300, 350, 400, 450, 650, 700, 950, 1000, 1150, 1200, 1200, 1400, 1450]),
                ("大江山口内宮", [850, 700, 650, 600, 500, 400, 350, 400, 450, 500, 700, 850, 1000, 1100, 1200, 1200, 1300, 1450, 1500]),
                ("二俣", [950, 800, 700, 600, 600, 450, 350, 450, 500, 600, 700, 850, 1000, 1150, 1200, 1300, 1400, 1500, 1500]),
                ("大江高校前", [950, 850, 700, 650, 650, 500, 400, 500, 600, 650, 800, 950, 1100, 1150, 1300, 1300, 1400, 1500, 1500]),
                ("大江", [1000, 850, 800, 650, 650, 500, 400, 500, 600, 650, 800, 950, 1100, 1200, 1300, 1400, 1400, 1500, 1500]),
                ("公庄", [1000, 950, 850, 700, 700, 600, 450, 600, 650, 700, 850, 1000, 1150, 1200, 1400, 1400, 1450, 1500, 1500]),
                ("下天津", [1100, 1000, 850, 800, 800, 650, 500, 650, 700, 800, 950, 1100, 1150, 1300, 1400, 1450, 1500, 1500, 1500]),
                ("牧", [1100, 1000, 950, 850, 800, 650, 600, 650, 800, 850, 1000, 1100, 1200, 1300, 1450, 1500, 1500, 1500, 1500]),
                ("荒河かしの木台", [1150, 1100, 1000, 950, 850, 700, 650, 700, 800, 850, 1000, 1150, 1300, 1400, 1450, 1500, 1500, 1500, 1500]),
                ("福知山市民病院口", [1150, 1100, 1000, 950, 950, 800, 650, 800, 850, 950, 1100, 1150, 1300, 1400, 1500, 1500, 1500, 1500, 1500]),
                ("福知山", [1200, 1100, 1100, 1000, 950, 800, 700, 800, 850, 950, 1100, 1150, 1300, 1450, 1500, 1500, 1500, 1500, 1500]),
            ],
        ),
    },
    {
        "key": "shinano_railway_station_pairs_202603",
        "operatorIds": ["しなの鉄道"],
        "operatorName": "しなの鉄道",
        "url": "https://www.shinanorailway.co.jp/rail-info/fare/docs/20260314_shinetsu.pdf",
        "notes": [
            "しなの鉄道公式の2026年3月14日旅客運賃表PDFから、しなの鉄道線（篠ノ井-軽井沢）と北しなの線（長野-妙高高原）の大人普通きっぷ運賃だけを収録。PDFにはJR信越線・篠ノ井線・小海線・飯山線、えちごトキめき鉄道との連絡運賃も併載されているが、旧データとの重複を避けるため会社線内だけを覆う。",
            "IC運賃、小児運賃、通勤・通学定期、乗継割引、JR/他社連絡運賃、企画券、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_B11683EC2A178F", "V4_ROUTE_0BF866A52922AE"],
        "pairs": station_pair_triangle_rows(
            [
                "篠ノ井",
                "屋代高校前",
                "屋代",
                "千曲",
                "戸倉",
                "坂城",
                "テクノさかき",
                "西上田",
                "上田",
                "信濃国分寺",
                "大屋",
                "田中",
                "滋野",
                "小諸",
                "平原",
                "御代田",
                "信濃追分",
                "中軽井沢",
                "軽井沢",
            ],
            [
                ("屋代高校前", [240]),
                ("屋代", [240, 190]),
                ("千曲", [250, 240, 190]),
                ("戸倉", [260, 250, 240, 190]),
                ("坂城", [350, 280, 260, 250, 240]),
                ("テクノさかき", [410, 320, 280, 260, 250, 190]),
                ("西上田", [480, 410, 370, 300, 260, 240, 240]),
                ("上田", [590, 500, 460, 410, 350, 260, 250, 240]),
                ("信濃国分寺", [630, 570, 520, 460, 410, 320, 260, 250, 190]),
                ("大屋", [700, 630, 590, 520, 480, 370, 320, 260, 240, 190]),
                ("田中", [760, 700, 650, 590, 540, 460, 390, 320, 250, 240, 240]),
                ("滋野", [850, 760, 720, 680, 610, 520, 460, 390, 300, 260, 250, 240]),
                ("小諸", [980, 900, 850, 810, 740, 650, 590, 520, 410, 370, 300, 260, 240]),
                ("平原", [1050, 980, 940, 870, 830, 740, 680, 610, 500, 430, 390, 300, 260, 240]),
                ("御代田", [1160, 1090, 1050, 980, 940, 850, 790, 720, 610, 540, 500, 430, 350, 250, 240]),
                ("信濃追分", [1290, 1230, 1180, 1120, 1070, 980, 920, 850, 740, 680, 630, 570, 480, 350, 280, 240]),
                ("中軽井沢", [1380, 1290, 1250, 1200, 1140, 1050, 980, 920, 810, 760, 700, 630, 540, 410, 350, 260, 240]),
                ("軽井沢", [1470, 1380, 1340, 1290, 1230, 1140, 1070, 1010, 900, 850, 790, 720, 630, 500, 430, 320, 250, 240]),
            ],
        )
        + station_pair_triangle_rows(
            [
                "妙高高原",
                "黒姫",
                "古間",
                "牟礼",
                "豊野",
                "三才",
                "北長野",
                "長野",
            ],
            [
                ("黒姫", [250]),
                ("古間", [300, 240]),
                ("牟礼", [430, 260, 250]),
                ("豊野", [610, 430, 350, 250]),
                ("三才", [700, 520, 430, 280, 240]),
                ("北長野", [760, 570, 500, 350, 250, 190]),
                ("長野", [850, 650, 590, 430, 260, 250, 240]),
            ],
        ),
    },
    {
        "key": "keihan_keishin_station_pairs_202510",
        "operatorIds": ["京阪電気鉄道"],
        "operatorName": "京阪電気鉄道",
        "url": "https://www.keihan.co.jp/traffic/station/assets/pdf/fare/500.pdf",
        "notes": [
            "京阪公式の各駅普通運賃・定期券運賃PDF（2025年10月1日改定）から、京津線内の御陵-びわ湖浜大津間大人普通運賃だけを収録。京都市営地下鉄線内（三条京阪-御陵）を含む連絡運賃、石山坂本線内運賃、定期券、小児運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_1CF5E8D0817EE3"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "御陵",
                "京阪山科",
                "四宮",
                "追分",
                "大谷",
                "上栄町",
                "びわ湖浜大津",
            ],
            [
                ("御陵", [200, 200, 200, 200, 280, 280]),
                ("京阪山科", [200, 200, 200, 280, 280]),
                ("四宮", [200, 200, 200, 280]),
                ("追分", [200, 200, 200]),
                ("大谷", [200, 200]),
                ("上栄町", [200]),
            ],
        ),
    },
    {
        "key": "wakasa_railway_station_pairs_202103",
        "operatorIds": ["若桜鉄道"],
        "operatorName": "若桜鉄道",
        "url": "https://wakatetsu.co.jp/wp/wp-content/uploads/2021/03/unchin-wakasa-20210313-3.svg",
        "notes": [
            "若桜鉄道公式の普通運賃 若桜-鳥取駅間SVGから、若桜鉄道線内（郡家-若桜）の大人普通運賃だけを収録。公式表の船岡はゲーム側駅名の因幡船岡に正規化している。",
            "鳥取・東郡家・津ノ井を含むJR因美線区間、小児運賃、JR連絡運賃、定期、1日フリー乗車券、親子きっぷ、シルバー/免許返納者割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_A7C27BDED2B61C"],
        "pairs": station_pair_triangle_rows(
            [
                "郡家",
                "八頭高校前",
                "因幡船岡",
                "隼",
                "安部",
                "八東",
                "徳丸",
                "丹比",
                "若桜",
            ],
            [
                ("八頭高校前", [100]),
                ("因幡船岡", [210, 170]),
                ("隼", [270, 270, 170]),
                ("安部", [300, 300, 270, 210]),
                ("八東", [340, 300, 300, 270, 210]),
                ("徳丸", [340, 340, 340, 300, 270, 170]),
                ("丹比", [370, 370, 340, 340, 300, 270, 170]),
                ("若桜", [440, 440, 400, 370, 370, 340, 300, 270]),
            ],
        ),
    },
    {
        "key": "kishu_railway_station_pairs_202601",
        "operatorIds": ["紀州鉄道"],
        "operatorName": "紀州鉄道",
        "url": "https://kitetsu.jp/railway/",
        "notes": [
            "紀州鉄道公式サイトの普通運賃表と近畿運輸局の業務監査資料にある初乗り120円・最長御坊-西御坊180円の普通旅客運賃体系から、ゲーム側5駅の大人普通運賃を収録。",
            "公式普通運賃表に明記されている西御坊-紀伊御坊120円、西御坊-学門150円、西御坊-JR御坊180円、紀伊御坊-JR御坊150円を基準に、公開キロ程（御坊0.0、学門1.5、紀伊御坊1.8、市役所前2.4、西御坊2.7km）で市役所前を含む短距離区間を同一普通運賃体系に補完している。",
            "小児運賃、定期、回数券、JR連絡運賃、障害者割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_19B10A93A20E24"],
        "pairs": station_pair_triangle_rows(
            ["御坊", "学門", "紀伊御坊", "市役所前", "西御坊"],
            [
                ("学門", [150]),
                ("紀伊御坊", [150, 120]),
                ("市役所前", [180, 120, 120]),
                ("西御坊", [180, 150, 120, 120]),
            ],
        ),
    },
    {
        "key": "tosakuro_gomen_nahari_station_pairs",
        "operatorIds": ["土佐くろしお鉄道"],
        "operatorName": "土佐くろしお鉄道",
        "url": "https://www.tosakuro.com/_files/ugd/310f5f_c30f6027c8894004a4c1e0618e5860ab.pdf",
        "notes": [
            "土佐くろしお鉄道公式のごめん・なはり線普通旅客運賃表PDFから、後免-奈半利間の大人普通運賃三角表を転記。",
            "ゲーム側の阿佐線 route には高知・土佐大津などJR土讃線側の駅が混在しているため、この表は土佐くろしお鉄道線内だけを覆い、JR区間は複合運賃解決に委ねる。",
            "小児運賃、定期運賃、割引乗車券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_7A9BB294C26921"],
        "pairs": station_pair_triangle_rows(
            [
                "後免",
                "後免町",
                "立田",
                "のいち",
                "よしかわ",
                "あかおか",
                "香我美",
                "夜須",
                "西分",
                "和食",
                "赤野",
                "穴内",
                "球場前",
                "あき総合病院前",
                "安芸",
                "伊尾木",
                "下山",
                "唐浜",
                "安田",
                "田野",
                "奈半利",
            ],
            [
                ("後免町", [210]),
                ("立田", [260, 210]),
                ("のいち", [260, 260, 210]),
                ("よしかわ", [410, 410, 260, 210]),
                ("あかおか", [410, 410, 410, 260, 210]),
                ("香我美", [410, 410, 410, 260, 260, 210]),
                ("夜須", [560, 410, 410, 410, 260, 260, 210]),
                ("西分", [560, 560, 560, 410, 410, 410, 260, 210]),
                ("和食", [560, 560, 560, 560, 410, 410, 410, 260, 210]),
                ("赤野", [720, 560, 560, 560, 410, 410, 410, 410, 260, 210]),
                ("穴内", [720, 720, 720, 560, 560, 560, 560, 410, 410, 260, 210]),
                ("球場前", [720, 720, 720, 720, 560, 560, 560, 560, 410, 410, 410, 210]),
                ("あき総合病院前", [720, 720, 720, 720, 560, 560, 560, 560, 410, 410, 410, 260, 210]),
                ("安芸", [920, 720, 720, 720, 720, 560, 560, 560, 410, 410, 410, 260, 210, 210]),
                ("伊尾木", [920, 920, 920, 720, 720, 720, 720, 560, 560, 560, 410, 410, 260, 260, 210]),
                ("下山", [920, 920, 920, 920, 720, 720, 720, 720, 560, 560, 560, 410, 410, 410, 410, 210]),
                ("唐浜", [1080, 1080, 920, 920, 920, 920, 720, 720, 720, 560, 560, 560, 410, 410, 410, 410, 210]),
                ("安田", [1080, 1080, 1080, 920, 920, 920, 920, 720, 720, 720, 720, 560, 560, 410, 410, 410, 260, 210]),
                ("田野", [1080, 1080, 1080, 1080, 920, 920, 920, 920, 720, 720, 720, 560, 560, 560, 560, 410, 410, 260, 210]),
                ("奈半利", [1080, 1080, 1080, 1080, 920, 920, 920, 920, 720, 720, 720, 720, 560, 560, 560, 560, 410, 260, 260, 210]),
            ],
        ),
    },
    {
        "key": "hanshin_namba_line_station_pairs_202603",
        "operatorIds": ["阪神電気鉄道"],
        "operatorName": "阪神電気鉄道",
        "url": "https://www.hanshin.co.jp/ticket/",
        "notes": [
            "阪神電気鉄道の2026年3月14日旅客営業規則の普通旅客運賃表に、公式サイト掲載の阪神なんば線加算運賃を加えて、尼崎-大阪難波間の大人普通運賃を収録。",
            "西九条-大阪難波の新線区間を含む場合は普通旅客運賃90円を加算し、乗車区間が1区内（1-4km）の場合は60円加算とする公式ルールを適用している。",
            "ゲーム側の阪神なんば線 route には近鉄奈良線側の駅が混在しているため、この表は阪神線内だけを覆い、近鉄区間は複合運賃解決に委ねる。定期、障害者割引、近鉄連絡運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_8B6754BA287621"],
        "pairs": station_pair_triangle_rows(
            ["尼崎", "大物", "出来島", "福", "伝法", "千鳥橋", "西九条", "九条", "ドーム前", "桜川", "大阪難波"],
            [
                ("大物", [160]),
                ("出来島", [160, 160]),
                ("福", [160, 160, 160]),
                ("伝法", [200, 160, 160, 160]),
                ("千鳥橋", [200, 200, 160, 160, 160]),
                ("西九条", [200, 200, 160, 160, 160, 160]),
                ("九条", [290, 290, 290, 290, 220, 220, 220]),
                ("ドーム前", [340, 290, 290, 290, 220, 220, 220, 220]),
                ("桜川", [340, 340, 290, 290, 290, 220, 220, 220, 220]),
                ("大阪難波", [340, 340, 290, 290, 290, 290, 220, 220, 220, 220]),
            ],
        ),
    },
    {
        "key": "odakyu_hakone_railway_line_station_pairs_202210",
        "operatorIds": ["小田急箱根"],
        "operatorName": "小田急箱根",
        "url": "https://www.hakonenavi.jp/assets/file/hakone-tozan_fee_221001.pdf",
        "notes": [
            "箱根登山鉄道電車旅客運賃表（2022年10月1日改定）の普通旅客運賃表から、小田原-強羅間の鉄道線大人普通運賃を転記。",
            "ゲーム側の鉄道線 route にはJR側の熱海が混在しているため、この表は小田急箱根の鉄道線内だけを覆い、JR区間は複合運賃解決に委ねる。",
            "小児運賃、団体割引、鋼索線、特急料金、フリーパス類は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_4983AA455EE72F"],
        "pairs": station_pair_triangle_rows(
            ["小田原", "箱根板橋", "風祭", "入生田", "箱根湯本", "塔ノ沢", "大平台", "宮ノ下", "小涌谷", "彫刻の森", "強羅"],
            [
                ("箱根板橋", [160]),
                ("風祭", [220, 160]),
                ("入生田", [260, 160, 160]),
                ("箱根湯本", [360, 260, 220, 160]),
                ("塔ノ沢", [420, 310, 360, 160, 160]),
                ("大平台", [510, 460, 460, 310, 220, 160]),
                ("宮ノ下", [670, 560, 560, 420, 310, 260, 160]),
                ("小涌谷", [710, 620, 620, 510, 420, 360, 220, 160]),
                ("彫刻の森", [770, 670, 620, 560, 460, 420, 260, 160, 160]),
                ("強羅", [770, 710, 710, 560, 460, 420, 310, 160, 160, 160]),
            ],
        ),
    },
    {
        "key": "izukyu_station_pairs_202603",
        "operatorIds": ["伊豆急行"],
        "operatorName": "伊豆急行",
        "url": "https://www.izukyu.co.jp/fares/index.php",
        "notes": [
            "伊豆急行公式の各駅運賃表（在来線経由・普通乗車券）から、伊東-伊豆急下田間の伊豆急行線内大人普通運賃だけを収録。東京・熱海側などJR区間、IC運賃、小児運賃、定期、特急料金・グリーン料金、企画券、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_57E5D5DC690C77"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "伊東",
                "南伊東",
                "川奈",
                "富戸",
                "城ヶ崎海岸",
                "伊豆高原",
                "伊豆大川",
                "伊豆北川",
                "伊豆熱川",
                "片瀬白田",
                "伊豆稲取",
                "今井浜海岸",
                "河津",
                "稲梓",
                "蓮台寺",
                "伊豆急下田",
            ],
            [
                ("伊東", [190, 370, 560, 650, 750, 1070, 1170, 1170, 1270, 1380, 1580, 1580, 1770, 1860, 1860]),
                ("南伊東", [250, 470, 560, 650, 960, 1070, 1170, 1170, 1380, 1480, 1480, 1680, 1770, 1860]),
                ("川奈", [280, 370, 470, 750, 860, 960, 960, 1170, 1380, 1380, 1580, 1680, 1680]),
                ("富戸", [190, 250, 470, 560, 650, 750, 960, 1170, 1170, 1380, 1480, 1580]),
                ("城ヶ崎海岸", [190, 370, 470, 560, 650, 860, 1070, 1070, 1270, 1380, 1480]),
                ("伊豆高原", [250, 370, 470, 560, 750, 960, 960, 1170, 1270, 1380]),
                ("伊豆大川", [190, 190, 280, 470, 650, 750, 960, 1170, 1170]),
                ("伊豆北川", [190, 190, 370, 560, 650, 860, 1070, 1170]),
                ("伊豆熱川", [190, 280, 470, 560, 860, 960, 1070]),
                ("片瀬白田", [250, 470, 470, 750, 860, 960]),
                ("伊豆稲取", [190, 250, 560, 650, 750]),
                ("今井浜海岸", [190, 370, 470, 560]),
                ("河津", [280, 470, 560]),
                ("稲梓", [190, 250]),
                ("蓮台寺", [190]),
            ],
        ),
    },
    {
        "key": "hapi_line_fukui_station_pairs_202603",
        "operatorIds": ["ハピラインふくい"],
        "operatorName": "ハピラインふくい",
        "url": "https://www.hapi-line.co.jp/files/uploads/%E6%99%AE%E9%80%9A%E6%97%85%E5%AE%A2%E9%81%8B%E8%B3%83%E8%A1%A8%EF%BC%88%E5%A4%A7%E4%BA%BA%EF%BC%89__4.pdf",
        "notes": [
            "ハピラインふくい公式の普通旅客運賃表（大人）PDFから、ハピラインふくい線自社区間（敦賀-大聖寺）の大人普通運賃だけを収録。JR越美北線・JR小浜線・IRいしかわ鉄道などとの連絡運賃、小児運賃、定期、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_2B86C267C5D97C"],
        "pairs": station_pair_triangle_rows(
            [
                "敦賀",
                "南今庄",
                "今庄",
                "湯尾",
                "南条",
                "王子保",
                "しきぶ",
                "武生",
                "鯖江",
                "北鯖江",
                "大土呂",
                "越前花堂",
                "福井",
                "森田",
                "春江",
                "丸岡",
                "芦原温泉",
                "細呂木",
                "牛ノ谷",
                "大聖寺",
            ],
            [
                ("南今庄", [380]),
                ("今庄", [380, 170]),
                ("湯尾", [480, 230, 220]),
                ("南条", [590, 230, 230, 220]),
                ("王子保", [680, 280, 280, 230, 220]),
                ("しきぶ", [680, 380, 280, 280, 230, 170]),
                ("武生", [780, 380, 380, 280, 230, 220, 170]),
                ("鯖江", [890, 480, 480, 380, 280, 230, 230, 220]),
                ("北鯖江", [890, 590, 480, 480, 380, 280, 280, 230, 220]),
                ("大土呂", [990, 680, 590, 590, 480, 380, 280, 280, 230, 220]),
                ("越前花堂", [1140, 680, 680, 590, 590, 480, 380, 380, 280, 230, 220]),
                ("福井", [1140, 780, 680, 680, 590, 480, 480, 380, 280, 280, 220, 170]),
                ("森田", [1140, 890, 890, 780, 680, 590, 590, 480, 380, 380, 280, 230, 220]),
                ("春江", [1350, 990, 890, 780, 780, 680, 590, 590, 480, 380, 280, 280, 230, 170]),
                ("丸岡", [1350, 990, 990, 890, 780, 780, 680, 680, 590, 480, 380, 280, 280, 220, 220]),
                ("芦原温泉", [1540, 1140, 1140, 990, 990, 890, 780, 780, 680, 590, 480, 480, 380, 280, 230, 220]),
                ("細呂木", [1540, 1140, 1140, 1140, 990, 890, 890, 890, 780, 680, 590, 480, 480, 380, 280, 230, 220]),
                ("牛ノ谷", [1540, 1350, 1140, 1140, 1140, 990, 990, 890, 780, 780, 680, 590, 480, 380, 380, 280, 230, 220]),
                ("大聖寺", [1750, 1350, 1350, 1350, 1140, 1140, 1140, 990, 890, 890, 780, 680, 680, 480, 480, 380, 280, 230, 220]),
            ],
        ),
    },
    {
        "key": "ainokaze_toyama_station_pairs_202509",
        "operatorIds": ["あいの風とやま鉄道"],
        "operatorName": "あいの風とやま鉄道",
        "url": "https://ainokaze.co.jp/faretable",
        "notes": [
            "あいの風とやま鉄道公式の駅別普通運賃HTML表から、石動-越中宮崎間の会社線内大人普通運賃だけを収録。IRいしかわ鉄道・えちごトキめき鉄道などとの連絡運賃、小児運賃、定期、ライナー券、ICカード固有の取扱い、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_FA49CAFAF442E8"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "石動",
                "福岡",
                "西高岡",
                "高岡やぶなみ",
                "高岡",
                "越中大門",
                "小杉",
                "呉羽",
                "富山",
                "新富山口",
                "東富山",
                "水橋",
                "滑川",
                "東滑川",
                "魚津",
                "黒部",
                "生地",
                "西入善",
                "入善",
                "泊",
                "越中宮崎",
            ],
            [
                ("石動", [240, 290, 290, 390, 390, 500, 600, 700, 810, 920, 1020, 1180, 1180, 1390, 1390, 1590, 1590, 1590, 1810, 1810]),
                ("福岡", [220, 240, 240, 290, 390, 500, 600, 700, 700, 810, 920, 1020, 1180, 1180, 1390, 1390, 1590, 1590, 1810]),
                ("西高岡", [170, 220, 240, 290, 390, 500, 600, 700, 810, 920, 920, 1020, 1180, 1180, 1390, 1390, 1590, 1590]),
                ("高岡やぶなみ", [170, 240, 240, 390, 500, 600, 600, 700, 810, 920, 1020, 1180, 1180, 1390, 1390, 1590, 1590]),
                ("高岡", [220, 240, 290, 390, 500, 600, 700, 810, 810, 920, 1180, 1180, 1180, 1390, 1390, 1590]),
                ("越中大門", [220, 290, 390, 390, 500, 600, 700, 810, 920, 1020, 1180, 1180, 1180, 1390, 1390]),
                ("小杉", [240, 290, 390, 390, 500, 600, 700, 810, 920, 1020, 1180, 1180, 1390, 1390]),
                ("呉羽", [220, 240, 290, 390, 500, 600, 700, 810, 920, 920, 1020, 1180, 1180]),
                ("富山", [220, 240, 290, 390, 500, 600, 700, 810, 810, 920, 1020, 1180]),
                ("新富山口", [170, 240, 290, 390, 500, 600, 700, 810, 810, 1020, 1020]),
                ("東富山", [220, 290, 290, 390, 600, 600, 700, 810, 920, 1020]),
                ("水橋", [220, 240, 290, 500, 500, 600, 700, 810, 920]),
                ("滑川", [220, 240, 290, 390, 500, 600, 700, 810]),
                ("東滑川", [220, 290, 390, 390, 500, 600, 700]),
                ("魚津", [240, 290, 290, 390, 500, 600]),
                ("黒部", [220, 240, 290, 390, 500]),
                ("生地", [220, 240, 290, 390]),
                ("西入善", [220, 240, 290]),
                ("入善", [220, 240]),
                ("泊", [220]),
            ],
        ),
    },
    {
        "key": "ir_ishikawa_station_pairs_202603",
        "operatorIds": ["irいしかわ鉄道"],
        "operatorName": "IRいしかわ鉄道",
        "url": "https://www.ishikawa-railway.jp/fare/pdf/futsuu_unchin20260314.pdf",
        "notes": [
            "IRいしかわ鉄道公式の2026年3月14日普通運賃表・大人PDFから、IRいしかわ鉄道会社線（倶利伽羅-大聖寺）の大人普通運賃だけを収録。JR七尾線、あいの風とやま鉄道、ハピラインふくいとの連絡運賃、小児運賃、定期、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_6BA3AC258124BF"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "倶利伽羅",
                "津幡",
                "森本",
                "東金沢",
                "金沢",
                "西金沢",
                "野々市",
                "松任",
                "西松任",
                "加賀笠間",
                "美川",
                "小舞子",
                "能美根上",
                "明峰",
                "小松",
                "粟津",
                "動橋",
                "加賀温泉",
                "大聖寺",
            ],
            [
                ("倶利伽羅", [230, 270, 370, 370, 480, 480, 580, 580, 670, 780, 780, 880, 880, 980, 1130, 1130, 1330, 1330]),
                ("津幡", [230, 230, 270, 370, 370, 480, 480, 580, 580, 670, 670, 780, 780, 980, 1130, 1130, 1130]),
                ("森本", [160, 220, 230, 270, 270, 370, 370, 480, 480, 580, 670, 670, 780, 880, 980, 1130]),
                ("東金沢", [160, 230, 230, 270, 270, 370, 480, 480, 580, 580, 670, 780, 880, 880, 980]),
                ("金沢", [220, 230, 230, 270, 270, 370, 370, 480, 580, 580, 670, 780, 880, 980]),
                ("西金沢", [160, 220, 230, 270, 270, 370, 370, 480, 480, 670, 780, 780, 880]),
                ("野々市", [220, 220, 230, 270, 270, 370, 370, 480, 580, 670, 780, 880]),
                ("松任", [160, 220, 230, 270, 270, 370, 370, 480, 580, 670, 780]),
                ("西松任", [160, 230, 230, 270, 270, 370, 480, 580, 670, 780]),
                ("加賀笠間", [220, 220, 230, 270, 270, 480, 580, 580, 670]),
                ("美川", [160, 220, 230, 270, 370, 480, 480, 580]),
                ("小舞子", [160, 220, 230, 270, 370, 480, 580]),
                ("能美根上", [160, 220, 270, 370, 370, 480]),
                ("明峰", [160, 230, 270, 370, 480]),
                ("小松", [220, 270, 270, 370]),
                ("粟津", [220, 230, 270]),
                ("動橋", [220, 230]),
                ("加賀温泉", [220]),
            ],
        ),
    },
    {
        "key": "echigo_tokimeki_station_pairs_202603",
        "operatorIds": ["えちごトキめき鉄道"],
        "operatorName": "えちごトキめき鉄道",
        "url": "https://www.echigo-tokimeki.co.jp/userfiles/elfinder/information/fare01_20260314.pdf",
        "notes": [
            "えちごトキめき鉄道公式の2026年3月14日普通旅客運賃表から、妙高高原-市振間の会社線内大人普通運賃（上段）だけを収録。下段小児運賃、しなの鉄道・あいの風とやま鉄道・北越急行・JR方面の連絡運賃、特急料金、定期、割引運賃は別体系のため未収録。",
            "妙高はねうまラインと日本海ひすいラインは同一会社内の駅間表として一体収録し、直江津をまたぐ会社線内移動も公式表の値を使用する。",
        ],
        "routeIds": ["V4_ROUTE_46917C106933E6", "V4_ROUTE_D74F1FD2957F19"],
        "pairs": station_pair_triangle_rows(
            [
                "妙高高原",
                "関山",
                "二本木",
                "新井",
                "北新井",
                "上越妙高",
                "南高田",
                "高田",
                "春日山",
                "直江津",
                "谷浜",
                "有間川",
                "名立",
                "筒石",
                "能生",
                "浦本",
                "梶屋敷",
                "えちご押上ひすい海岸",
                "糸魚川",
                "青海",
                "親不知",
                "市振",
            ],
            [
                ("関山", [330]),
                ("二本木", [400, 330]),
                ("新井", [650, 400, 330]),
                ("北新井", [650, 510, 330, 220]),
                ("上越妙高", [790, 650, 400, 330, 300]),
                ("南高田", [790, 650, 400, 330, 300, 220]),
                ("高田", [920, 650, 510, 330, 330, 300, 220]),
                ("春日山", [920, 790, 650, 400, 400, 330, 300, 300]),
                ("直江津", [1070, 920, 650, 510, 400, 400, 330, 330, 220]),
                ("谷浜", [1210, 1070, 790, 650, 650, 510, 510, 400, 330, 330]),
                ("有間川", [1350, 1210, 920, 790, 650, 650, 510, 510, 400, 330, 300]),
                ("名立", [1540, 1350, 1070, 920, 790, 650, 650, 650, 510, 400, 330, 300]),
                ("筒石", [1540, 1350, 1210, 1070, 920, 790, 790, 790, 650, 510, 400, 330, 300]),
                ("能生", [1830, 1540, 1350, 1210, 1070, 1070, 920, 920, 790, 790, 510, 510, 400, 330]),
                ("浦本", [1830, 1830, 1540, 1350, 1210, 1210, 1070, 1070, 920, 920, 650, 650, 510, 400, 300]),
                ("梶屋敷", [2100, 1830, 1540, 1540, 1350, 1210, 1210, 1210, 1070, 920, 790, 650, 650, 510, 330, 300]),
                ("えちご押上ひすい海岸", [2100, 1830, 1830, 1540, 1540, 1350, 1350, 1210, 1070, 1070, 920, 790, 650, 510, 400, 330, 220]),
                ("糸魚川", [2100, 2100, 1830, 1540, 1540, 1350, 1350, 1350, 1210, 1070, 920, 790, 650, 650, 400, 330, 300, 220]),
                ("青海", [2390, 2100, 1830, 1830, 1540, 1540, 1540, 1540, 1350, 1350, 1070, 1070, 920, 790, 510, 400, 400, 330, 330]),
                ("親不知", [2390, 2390, 2100, 1830, 1830, 1830, 1540, 1540, 1540, 1540, 1210, 1210, 1070, 920, 650, 510, 510, 400, 400, 300]),
                ("市振", [2660, 2660, 2390, 2100, 2100, 1830, 1830, 1830, 1830, 1540, 1540, 1350, 1350, 1210, 920, 790, 650, 650, 650, 400, 330]),
            ],
        ),
    },
    {
        "key": "aizu_railway_station_pairs_201910",
        "operatorIds": ["会津鉄道"],
        "operatorName": "会津鉄道",
        "url": "https://aizutetsudo.jp/wp-content/uploads/2026/03/%E9%81%8B%E8%B3%83%E8%A1%A8No2.pdf",
        "notes": [
            "会津鉄道公式の駅間普通旅客運賃表（2019年10月1日、大人運賃は上段）から、西若松-会津高原尾瀬口間の会津鉄道線内大人普通運賃だけを収録。会津若松-西若松のJR区間、野岩鉄道・東武方面の連絡運賃、小児運賃、定期、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_7B9216D63221DA"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "西若松",
                "南若松",
                "門田",
                "あまや",
                "芦ノ牧温泉",
                "大川ダム公園",
                "芦ノ牧温泉南",
                "湯野上温泉",
                "塔のへつり",
                "弥五島",
                "会津下郷",
                "ふるさと公園",
                "養鱒公園",
                "会津長野",
                "田島高校前",
                "会津田島",
                "中荒井",
                "会津荒海",
                "会津山村道場",
                "七ケ岳登山口",
                "会津高原尾瀬口",
            ],
            [
                ("西若松", [200, 270, 310, 420, 630, 630, 860, 960, 1070, 1170, 1170, 1280, 1390, 1500, 1500, 1650, 1710, 1710, 1770, 1910]),
                ("南若松", [200, 270, 310, 520, 520, 740, 860, 960, 1070, 1070, 1170, 1280, 1390, 1390, 1570, 1650, 1650, 1710, 1830]),
                ("門田", [200, 270, 420, 520, 630, 860, 860, 960, 1070, 1170, 1170, 1280, 1390, 1500, 1570, 1650, 1710, 1770]),
                ("あまや", [200, 310, 420, 520, 740, 740, 860, 960, 1070, 1070, 1170, 1280, 1390, 1500, 1570, 1650, 1710]),
                ("芦ノ牧温泉", [270, 310, 520, 630, 630, 740, 860, 960, 960, 1070, 1170, 1280, 1390, 1500, 1570, 1650]),
                ("大川ダム公園", [200, 310, 420, 420, 520, 630, 740, 860, 860, 960, 1070, 1170, 1280, 1390, 1500]),
                ("芦ノ牧温泉南", [270, 310, 420, 520, 520, 630, 740, 860, 960, 1070, 1170, 1170, 1280, 1500]),
                ("湯野上温泉", [270, 270, 310, 420, 520, 520, 630, 740, 860, 960, 1070, 1170, 1280]),
                ("塔のへつり", [200, 270, 270, 310, 420, 520, 630, 740, 860, 860, 960, 1170]),
                ("弥五島", [270, 270, 310, 420, 420, 520, 630, 860, 860, 960, 1070]),
                ("会津下郷", [200, 270, 310, 310, 420, 520, 740, 740, 860, 960]),
                ("ふるさと公園", [200, 270, 310, 420, 520, 630, 630, 740, 960]),
                ("養鱒公園", [200, 270, 310, 420, 520, 520, 630, 860]),
                ("会津長野", [200, 270, 310, 420, 520, 630, 740]),
                ("田島高校前", [200, 310, 420, 420, 520, 630]),
                ("会津田島", [270, 310, 310, 420, 630]),
                ("中荒井", [270, 270, 310, 420]),
                ("会津荒海", [200, 270, 310]),
                ("会津山村道場", [200, 310]),
                ("七ケ岳登山口", [270]),
            ],
        ),
    },
    {
        "key": "minamiaso_railway_station_pairs_202604",
        "operatorIds": ["南阿蘇鉄道"],
        "operatorName": "南阿蘇鉄道",
        "url": "https://www.mt-torokko.com/information/fare/",
        "notes": [
            "南阿蘇鉄道公式の普通運賃検索HTMLに埋め込まれた運賃表から、高森-立野間の高森線大人普通運賃だけを収録。小児運賃、トロッコ列車料金、サニー号座席指定券、JR連絡運輸、定期、回数券、フリーきっぷ、団体・特殊割引、手回り料金は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_139564287D8A09"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "高森",
                "見晴台",
                "南阿蘇白川水源",
                "阿蘇白川",
                "中松",
                "白水高原",
                "阿蘇下田",
                "加勢",
                "長陽",
                "立野",
            ],
            [
                ("高森", [180, 210, 240, 290, 350, 390, 390, 430, 490]),
                ("見晴台", [180, 210, 240, 290, 350, 390, 390, 490]),
                ("南阿蘇白川水源", [180, 210, 240, 290, 350, 350, 460]),
                ("阿蘇白川", [210, 240, 290, 290, 350, 430]),
                ("中松", [180, 210, 240, 240, 390]),
                ("白水高原", [180, 210, 240, 350]),
                ("阿蘇下田", [180, 210, 290]),
                ("加勢", [180, 240]),
                ("長陽", [240]),
            ],
        ),
    },
    {
        "key": "ise_railway_station_pairs_202605",
        "operatorIds": ["伊勢鉄道"],
        "operatorName": "伊勢鉄道",
        "url": "https://isetetu.co.jp/fare/",
        "notes": [
            "伊勢鉄道公式の運賃検索（普通旅客運賃）から、河原田-津間の伊勢鉄道線内大人普通運賃だけを収録。四日市-河原田のJR区間、回数券、定期券、特急料金、入場券、手回り品料金、障害者割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_AC280F92B606C9"],
        "pairs": station_pair_triangle_rows(
            [
                "河原田",
                "鈴鹿",
                "玉垣",
                "鈴鹿サーキット稲生",
                "徳田",
                "中瀬古",
                "伊勢上野",
                "河芸",
                "東一身田",
                "津",
            ],
            [
                ("鈴鹿", [220]),
                ("玉垣", [260, 220]),
                ("鈴鹿サーキット稲生", [300, 220, 180]),
                ("徳田", [300, 260, 220, 180]),
                ("中瀬古", [360, 260, 220, 220, 180]),
                ("伊勢上野", [360, 300, 260, 220, 180, 180]),
                ("河芸", [400, 360, 300, 260, 220, 220, 180]),
                ("東一身田", [440, 400, 360, 300, 260, 260, 220, 180]),
                ("津", [520, 440, 400, 360, 300, 300, 260, 220, 180]),
            ],
        ),
    },
    {
        "key": "abukuma_express_station_pairs_201910",
        "operatorIds": ["阿武隈急行"],
        "operatorName": "阿武隈急行",
        "url": "https://www.abukyu.co.jp/direction/wp-content/uploads/2019/09/unchin_201910.pdf",
        "notes": [
            "阿武隈急行公式の普通運賃表（令和元年10月1日改正）から、福島-槻木間の阿武隈急行線内大人普通運賃だけを収録。公式表の学院前は福島学院前、公園前はやながわ希望の森公園前に正規化。仙台-槻木などJR区間、小児運賃、定期、連絡運賃、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_989C2E5FA4C9FB"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "福島",
                "卸町",
                "福島学院前",
                "瀬上",
                "向瀬上",
                "高子",
                "上保原",
                "保原",
                "大泉",
                "二井田",
                "新田",
                "梁川",
                "やながわ希望の森公園前",
                "富野",
                "兜",
                "あぶくま",
                "丸森",
                "北丸森",
                "南角田",
                "角田",
                "横倉",
                "岡",
                "東船岡",
                "槻木",
            ],
            [
                ("福島", [260, 260, 330, 330, 400, 400, 460, 460, 510, 510, 570, 570, 620, 660, 700, 810, 850, 850, 880, 920, 920, 960, 980]),
                ("卸町", [180, 180, 180, 260, 260, 330, 330, 400, 400, 460, 460, 510, 570, 620, 740, 780, 780, 810, 850, 880, 920, 940]),
                ("福島学院前", [180, 180, 260, 260, 330, 330, 330, 400, 400, 460, 510, 570, 620, 740, 740, 780, 810, 810, 850, 880, 940]),
                ("瀬上", [180, 180, 260, 260, 330, 330, 400, 400, 460, 460, 510, 620, 700, 740, 780, 780, 810, 850, 880, 920]),
                ("向瀬上", [180, 180, 260, 260, 330, 330, 400, 400, 460, 510, 570, 700, 740, 740, 780, 810, 850, 880, 920]),
                ("高子", [180, 180, 260, 260, 330, 330, 400, 400, 510, 570, 700, 700, 740, 780, 780, 810, 850, 880]),
                ("上保原", [180, 180, 260, 260, 330, 330, 400, 460, 510, 660, 700, 740, 740, 780, 810, 850, 880]),
                ("保原", [180, 180, 260, 260, 330, 400, 460, 510, 660, 660, 700, 740, 740, 780, 810, 880]),
                ("大泉", [180, 260, 260, 330, 330, 400, 510, 620, 660, 700, 700, 740, 780, 810, 850]),
                ("二井田", [180, 180, 260, 330, 400, 460, 620, 620, 660, 700, 700, 740, 780, 850]),
                ("新田", [180, 180, 260, 330, 460, 570, 620, 660, 660, 700, 740, 780, 810]),
                ("梁川", [180, 260, 330, 400, 570, 570, 620, 660, 660, 700, 740, 810]),
                ("やながわ希望の森公園前", [180, 260, 400, 510, 570, 620, 620, 660, 700, 740, 780]),
                ("富野", [260, 330, 510, 510, 570, 620, 620, 660, 700, 740]),
                ("兜", [260, 460, 460, 510, 570, 570, 620, 660, 700]),
                ("あぶくま", [330, 400, 460, 460, 510, 570, 620, 660]),
                ("丸森", [180, 260, 260, 330, 400, 460, 510]),
                ("北丸森", [180, 260, 260, 330, 460, 510]),
                ("南角田", [180, 260, 330, 400, 460]),
                ("角田", [180, 260, 330, 400]),
                ("横倉", [180, 330, 400]),
                ("岡", [260, 330]),
                ("東船岡", [260]),
            ],
        ),
    },
    {
        "key": "chizu_express_station_pairs_202605",
        "operatorIds": ["智頭急行"],
        "operatorName": "智頭急行",
        "url": "https://www.chizukyu.co.jp/chizukyu/jikoku_unchin/futuressya/",
        "notes": [
            "智頭急行公式の普通列車各駅発運賃表から、上郡-智頭間の智頭線内大人普通運賃だけを収録。鳥取・倉吉・岡山・姫路・京阪神側などJR区間、特急料金、通勤・通学定期、小児運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_977F4086D306F8"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "上郡",
                "苔縄",
                "河野原円心",
                "久崎",
                "佐用",
                "平福",
                "石井",
                "宮本武蔵",
                "大原",
                "西粟倉",
                "あわくら温泉",
                "山郷",
                "恋山形",
                "智頭",
            ],
            [
                ("上郡", [240, 310, 430, 500, 630, 750, 810, 880, 950, 1010, 1130, 1190, 1320]),
                ("苔縄", [180, 310, 430, 500, 630, 690, 750, 810, 880, 1070, 1130, 1250]),
                ("河野原円心", [240, 370, 500, 570, 630, 690, 750, 880, 1010, 1070, 1190]),
                ("久崎", [240, 370, 430, 570, 570, 690, 750, 880, 950, 1070]),
                ("佐用", [240, 370, 430, 500, 570, 630, 750, 810, 950]),
                ("平福", [240, 310, 370, 430, 570, 690, 750, 880]),
                ("石井", [240, 310, 370, 430, 570, 630, 750]),
                ("宮本武蔵", [180, 310, 370, 500, 570, 690]),
                ("大原", [240, 310, 430, 500, 630]),
                ("西粟倉", [240, 370, 430, 570]),
                ("あわくら温泉", [310, 370, 500]),
                ("山郷", [180, 310]),
                ("恋山形", [310]),
            ],
        ),
    },
    {
        "key": "fukui_railway_station_pairs_202403",
        "operatorIds": ["福井鉄道"],
        "operatorName": "福井鉄道",
        "url": "https://fukutetsu.jp/train/pdf/unchin_futuu.pdf",
        "notes": [
            "福井鉄道公式の普通旅客運賃表（2024年3月16日改定）から、たけふ新-田原町間の福武線内大人普通運賃だけを収録。鷲塚針原-田原町のえちぜん鉄道区間、小児運賃、連絡運賃、定期、割引券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_F2896B3A5449BD"],
        "pairs": station_pair_triangle_rows(
            [
                "たけふ新",
                "北府",
                "スポーツ公園",
                "家久",
                "サンドーム西",
                "西鯖江",
                "西山公園",
                "水落",
                "神明",
                "鳥羽中",
                "三十八社",
                "泰澄の里",
                "浅水",
                "ハーモニーホール",
                "清明",
                "江端",
                "ベル前",
                "花堂",
                "赤十字前",
                "商工会議所前",
                "足羽山公園口",
                "福井城址大名町",
                "福井駅",
                "仁愛女子高校",
                "田原町",
            ],
            [
                ("北府", [210]),
                ("スポーツ公園", [210, 210]),
                ("家久", [260, 210, 210]),
                ("サンドーム西", [260, 260, 260, 210]),
                ("西鯖江", [310, 310, 260, 260, 210]),
                ("西山公園", [310, 310, 310, 260, 210, 210]),
                ("水落", [340, 340, 310, 310, 260, 210, 210]),
                ("神明", [390, 340, 340, 340, 310, 260, 260, 210]),
                ("鳥羽中", [390, 390, 340, 340, 310, 310, 260, 260, 210]),
                ("三十八社", [420, 420, 390, 390, 340, 310, 310, 260, 260, 210]),
                ("泰澄の里", [420, 420, 420, 390, 340, 340, 310, 310, 260, 260, 210]),
                ("浅水", [430, 430, 420, 420, 390, 340, 340, 310, 310, 260, 260, 210]),
                ("ハーモニーホール", [430, 430, 430, 420, 390, 390, 340, 340, 310, 310, 260, 210, 210]),
                ("清明", [440, 440, 430, 430, 420, 390, 390, 340, 340, 310, 260, 260, 210, 210]),
                ("江端", [440, 440, 430, 430, 420, 420, 390, 390, 340, 310, 310, 260, 260, 210, 210]),
                ("ベル前", [450, 440, 440, 430, 420, 420, 420, 390, 340, 340, 310, 260, 260, 260, 210, 210]),
                ("花堂", [450, 450, 440, 440, 430, 420, 420, 390, 390, 340, 310, 310, 260, 260, 210, 210, 210]),
                ("赤十字前", [450, 450, 450, 440, 430, 430, 420, 420, 390, 390, 340, 310, 310, 260, 260, 260, 210, 210]),
                ("商工会議所前", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210]),
                ("足羽山公園口", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210, 180]),
                ("福井城址大名町", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210, 180, 180]),
                ("福井駅", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210, 180, 180, 180]),
                ("仁愛女子高校", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210, 180, 180, 180, 180]),
                ("田原町", [450, 450, 450, 450, 450, 430, 430, 430, 430, 430, 400, 370, 370, 310, 310, 310, 260, 260, 210, 180, 180, 180, 180, 180]),
            ],
        ),
    },
    {
        "key": "igr_iwate_ginga_station_pairs_202303",
        "operatorIds": ["アイジアルいわて銀河鉄道"],
        "operatorName": "アイジーアールいわて銀河鉄道",
        "url": "https://igr.jp/fare",
        "notes": [
            "IGRいわて銀河鉄道公式の普通運賃表（大人、2023年3月18日改定）から、盛岡-目時間の会社線内大人普通運賃だけを収録。ページには連絡運輸範囲表も併載されているが、v4では旧データとの重複を避けるためIGR線内の station-pair だけを覆う。",
            "小児運賃、通勤・通学定期、連絡運輸、割引乗車券、企画乗車券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_C7A3C3100D6667"],
        "pairs": station_pair_triangle_rows(
            [
                "盛岡",
                "青山",
                "厨川",
                "巣子",
                "滝沢",
                "渋民",
                "好摩",
                "岩手川口",
                "いわて沼宮内",
                "御堂",
                "奥中山高原",
                "小繋",
                "小鳥谷",
                "一戸",
                "二戸",
                "斗米",
                "金田一温泉",
                "目時",
            ],
            [
                ("青山", [230]),
                ("厨川", [320, 230]),
                ("巣子", [410, 340, 320]),
                ("滝沢", [410, 340, 340, 170]),
                ("渋民", [550, 410, 410, 340, 320]),
                ("好摩", [690, 550, 550, 410, 340, 320]),
                ("岩手川口", [830, 690, 690, 550, 410, 410, 320]),
                ("いわて沼宮内", [970, 830, 830, 690, 550, 550, 410, 320]),
                ("御堂", [1110, 970, 970, 830, 830, 690, 550, 410, 320]),
                ("奥中山高原", [1240, 1240, 1110, 970, 970, 830, 690, 550, 410, 340]),
                ("小繋", [1490, 1370, 1370, 1240, 1110, 1110, 970, 830, 690, 410, 340]),
                ("小鳥谷", [1610, 1610, 1490, 1370, 1370, 1240, 1110, 970, 830, 690, 550, 340]),
                ("一戸", [1730, 1730, 1610, 1490, 1490, 1370, 1240, 1110, 970, 830, 690, 410, 320]),
                ("二戸", [1970, 1850, 1850, 1730, 1610, 1490, 1370, 1240, 1110, 970, 830, 550, 410, 340]),
                ("斗米", [1970, 1970, 1850, 1730, 1730, 1610, 1490, 1370, 1240, 1110, 830, 690, 410, 340, 230]),
                ("金田一温泉", [2090, 2090, 1970, 1850, 1850, 1730, 1610, 1490, 1370, 1240, 970, 830, 550, 410, 340, 320]),
                ("目時", [2420, 2090, 2090, 1970, 1850, 1850, 1730, 1610, 1370, 1240, 1110, 830, 690, 550, 410, 340, 230]),
            ],
        ),
    },
    {
        "key": "yagan_railway_station_pairs_201910",
        "operatorIds": ["野岩鉄道"],
        "operatorName": "野岩鉄道",
        "url": "https://www.yagan.co.jp/fare/",
        "notes": [
            "野岩鉄道公式の会津鬼怒川線片道普通運賃表（令和元年10月1日改正）から、上段の大人普通運賃だけを収録。下段小人運賃、定期、得割回数券、特急料金、東武・会津鉄道・JR連絡乗車券、障害者割引は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_1DDEC07EC08E3A"],
        "pairs": station_pair_triangle_rows(
            [
                "新藤原",
                "龍王峡",
                "川治温泉",
                "川治湯元",
                "湯西川温泉",
                "中三依温泉",
                "上三依塩原温泉口",
                "男鹿高原",
                "会津高原尾瀬口",
            ],
            [
                ("龍王峡", [200]),
                ("川治温泉", [300, 300]),
                ("川治湯元", [300, 300, 200]),
                ("湯西川温泉", [520, 420, 300, 300]),
                ("中三依温泉", [740, 740, 520, 520, 420]),
                ("上三依塩原温泉口", [840, 840, 740, 640, 520, 300]),
                ("男鹿高原", [1000, 920, 840, 840, 640, 420, 300]),
                ("会津高原尾瀬口", [1090, 1090, 1000, 1000, 840, 640, 520, 300]),
            ],
        ),
    },
    {
        "key": "manyosen_station_pairs_202405",
        "operatorIds": ["万葉線"],
        "operatorName": "万葉線",
        "url": "https://www.manyosen.co.jp/timetable/fare/",
        "notes": [
            "万葉線公式の運賃表ページに掲載された2024年5月2日更新の普通運賃表画像から、大人普通運賃の全駅間三角表を収録。小児運賃、障がい者運賃、回数券、定期券、企画乗車券は別体系のため未収録。",
            "公式画像の省略表記「急患医療」は「急患医療センター前」、「志貴野」は「志貴野中学校前」に展開し、画像上の「クロスベイ前」はゲーム側駅名「第一イン新湊クロスベイ前」に正規化している。",
        ],
        "routeIds": ["V4_ROUTE_FD8F3149D9286F", "V4_ROUTE_2F68FEE8F4B65C"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "高岡駅",
                "末広町",
                "片原町",
                "坂下町",
                "急患医療センター前",
                "広小路",
                "志貴野中学校前",
                "市民病院前",
                "江尻",
                "旭ヶ丘",
                "荻布",
                "新能町",
                "米島口",
                "能町口",
                "新吉久",
                "吉久",
                "中伏木",
                "六渡寺",
                "庄川口",
                "第一イン新湊クロスベイ前",
                "新町口",
                "中新湊",
                "東新湊",
                "海王丸",
                "越ノ潟",
            ],
            [
                ("高岡駅", [200, 200, 200, 200, 200, 200, 250, 250, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400, 400, 400]),
                ("末広町", [200, 200, 200, 200, 200, 200, 250, 250, 250, 250, 250, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400, 400, 400]),
                ("片原町", [200, 200, 200, 200, 200, 250, 250, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400, 400]),
                ("坂下町", [200, 200, 200, 200, 250, 250, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400, 400]),
                ("急患医療センター前", [200, 200, 200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400, 400]),
                ("広小路", [200, 200, 200, 200, 250, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400, 400]),
                ("志貴野中学校前", [200, 200, 200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400]),
                ("市民病院前", [200, 200, 200, 200, 200, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400, 400]),
                ("江尻", [200, 200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400]),
                ("旭ヶ丘", [200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400, 400]),
                ("荻布", [200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400, 400]),
                ("新能町", [200, 200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 400, 400]),
                ("米島口", [200, 200, 250, 250, 250, 300, 300, 300, 350, 350, 350, 400]),
                ("能町口", [200, 200, 200, 250, 250, 250, 300, 300, 350, 350, 350]),
                ("新吉久", [200, 200, 200, 250, 250, 250, 300, 300, 350, 350]),
                ("吉久", [200, 200, 200, 250, 250, 250, 300, 300, 350]),
                ("中伏木", [200, 200, 200, 250, 250, 300, 300, 300]),
                ("六渡寺", [200, 200, 200, 250, 250, 300, 300]),
                ("庄川口", [200, 200, 200, 250, 250, 300]),
                ("第一イン新湊クロスベイ前", [200, 200, 250, 250, 250]),
                ("新町口", [200, 200, 250, 250]),
                ("中新湊", [200, 200, 250]),
                ("東新湊", [200, 200]),
                ("海王丸", [200]),
            ],
        ),
    },
    {
        "key": "noto_railway_station_pair_special_201910",
        "operatorIds": ["のと鉄道"],
        "operatorName": "のと鉄道",
        "url": "https://nototetsu.jp/wp-content/uploads/2022/12/2019.10kaisei-ninka.pdf",
        "notes": [
            "のと鉄道公式の2019年10月1日改定認可PDFに掲載された七尾-和倉温泉間の特定運賃190円を収録。通常の対キロ区間制とは別体系のため、この駅間だけ station-pair 特例として扱う。",
        ],
        "routeIds": ["V4_ROUTE_5F3470AE16E598"],
        "pairs": [("七尾", "和倉温泉", 190)],
    },
    {
        "key": "kotoden_station_pair_special_202305",
        "operatorIds": ["高松琴平電気鉄道"],
        "operatorName": "高松琴平電気鉄道",
        "url": "https://www.kotoden.co.jp/publichtm/kotoden/fare/image/kiro.pdf",
        "notes": [
            "高松琴平電気鉄道公式の2023年5月20日改定・普通旅客運賃表に明記された特定区間の大人普通運賃だけを収録。通常の営業キロ区間制とは別体系のため station-pair 特例として扱う。",
        ],
        "routeIds": ["V4_ROUTE_A45E51F5787C3A", "V4_ROUTE_23B25267C45ED3", "V4_ROUTE_D647E5F3ACC083"],
        "pairs": [
            ("高松築港", "八栗", 390),
            ("高松築港", "六万寺", 390),
            ("片原町", "六万寺", 390),
            ("高松築港", "大町", 420),
            ("高松築港", "八栗新道", 420),
            ("片原町", "八栗新道", 420),
            ("高松築港", "琴電志度", 500),
        ],
    },
    {
        "key": "keihan_iwashimizu_cable_station_pair_2026",
        "operatorIds": ["京阪電気鉄道"],
        "operatorName": "京阪電気鉄道",
        "url": "https://www.keihan.co.jp/traffic/time-fare/iwashimizu.html",
        "notes": [
            "京阪電気鉄道公式の石清水八幡宮参道ケーブル運賃・時刻表ページに掲載された普通運賃の大人片道300円を収録。往復運賃、小児運賃、通勤・通学定期運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_D6C48165646C89"],
        "pairs": [("ケーブル八幡宮口", "ケーブル八幡宮山上", 300)],
    },
    {
        "key": "daitetsu_ikawa_line_station_pairs_2026",
        "operatorIds": ["大井川鐵道"],
        "operatorName": "大井川鐵道",
        "url": "https://daitetsu.jp/ft_ikawa",
        "notes": [
            "大井川鐵道公式の井川線（南アルプスあぷとライン）運賃表から大人普通運賃の駅間三角表を転記。大井川本線はゲーム側が千頭-金谷の全線構造を保持している一方、現行公式ページは大井川本線・代行区間を分けているため、この表では井川線だけを覆う。",
        ],
        "routeIds": ["V4_ROUTE_0744003A7A9F3E"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "千頭",
                "川根両国",
                "沢間",
                "土本",
                "川根小山",
                "奥泉",
                "アプトいちしろ",
                "長島ダム",
                "ひらんだ",
                "奥大井湖上",
                "接岨峡温泉",
                "尾盛",
                "閑蔵",
                "井川",
            ],
            [
                ("千頭", [160, 160, 210, 310, 420, 520, 620, 670, 720, 830, 930, 1080, 1340]),
                ("川根両国", [160, 160, 260, 360, 470, 570, 620, 670, 780, 880, 1030, 1290]),
                ("沢間", [160, 210, 310, 420, 470, 570, 620, 720, 830, 980, 1240]),
                ("土本", [160, 210, 310, 420, 470, 520, 620, 720, 880, 1140]),
                ("川根小山", [160, 260, 310, 360, 470, 520, 620, 780, 1030]),
                ("奥泉", [160, 210, 310, 360, 420, 570, 670, 930]),
                ("アプトいちしろ", [160, 160, 210, 310, 420, 570, 830]),
                ("長島ダム", [160, 160, 260, 360, 520, 780]),
                ("ひらんだ", [160, 160, 310, 420, 670]),
                ("奥大井湖上", [160, 210, 360, 620]),
                ("接岨峡温泉", [160, 260, 520]),
                ("尾盛", [160, 420]),
                ("閑蔵", [260]),
            ],
        ),
    },
    {
        "key": "eizan_electric_railway_station_pairs_202304",
        "operatorIds": ["叡山電鉄"],
        "operatorName": "叡山電鉄",
        "url": "https://eizandensha.co.jp/wp-content/uploads/2023/03/01-fare_2023.04.01-b.pdf",
        "notes": [
            "叡山電鉄公式の2023年4月1日改定・旅客運賃表から、大人普通旅客運賃の駅間三角表を転記。表記はゲーム側の駅名に合わせて宝ケ池を宝ヶ池に正規化し、小児、定期、団体、PiTaPa割引、連絡定期、手回り品、入場料は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_C4A095641C7476", "V4_ROUTE_584583E19E9C3C"],
        "pairs": station_pair_triangle_rows(
            [
                "出町柳",
                "元田中",
                "茶山・京都芸術大学",
                "一乗寺",
                "修学院",
                "宝ヶ池",
                "三宅八幡",
                "八瀬比叡山口",
                "八幡前",
                "岩倉",
                "木野",
                "京都精華大前",
                "二軒茶屋",
                "市原",
                "二ノ瀬",
                "貴船口",
                "鞍馬",
            ],
            [
                ("元田中", [220]),
                ("茶山・京都芸術大学", [220, 220]),
                ("一乗寺", [220, 220, 220]),
                ("修学院", [220, 220, 220, 220]),
                ("宝ヶ池", [280, 280, 280, 280, 220]),
                ("三宅八幡", [280, 280, 280, 280, 220, 220]),
                ("八瀬比叡山口", [280, 280, 280, 280, 220, 220, 220]),
                ("八幡前", [280, 280, 280, 280, 220, 220, 280, 280]),
                ("岩倉", [280, 280, 280, 280, 220, 220, 280, 280, 220]),
                ("木野", [350, 350, 350, 350, 280, 280, 350, 350, 280, 220]),
                ("京都精華大前", [350, 350, 350, 350, 280, 280, 350, 350, 280, 220, 220]),
                ("二軒茶屋", [350, 350, 350, 350, 280, 280, 350, 350, 280, 220, 220, 220]),
                ("市原", [410, 410, 410, 410, 350, 350, 410, 410, 350, 280, 280, 280, 220]),
                ("二ノ瀬", [410, 410, 410, 410, 350, 350, 410, 410, 350, 280, 280, 280, 220, 220]),
                ("貴船口", [470, 470, 470, 470, 410, 410, 470, 470, 410, 350, 350, 350, 280, 280, 220]),
                ("鞍馬", [470, 470, 470, 470, 410, 410, 470, 470, 410, 350, 350, 350, 280, 280, 220, 220]),
            ],
        ),
    },
    {
        "key": "kumamoto_electric_railway_station_pairs_202510",
        "operatorIds": ["熊本電気鉄道"],
        "operatorName": "熊本電気鉄道",
        "url": "https://www.kumamotodentetsu.co.jp/ticket/futsu/index.html",
        "notes": [
            "熊本電気鉄道公式の普通運賃ページに掲載された令和7年10月1日実施の電車駅間運賃表画像から、大人普通運賃だけを転記。菊池線と藤崎線の分岐を含む全18駅の駅間表として収録し、小児運賃、IC/障がい者割引、バス運賃、定期券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_1DE3774E9461DB", "V4_ROUTE_98649C0CFD9833"],
        "pairs": station_pair_triangle_rows(
            [
                "上熊本",
                "韓々坂",
                "池田",
                "打越",
                "坪井川公園",
                "北熊本",
                "亀井",
                "八景水谷",
                "堀川",
                "新須屋",
                "須屋",
                "三ツ石",
                "黒石",
                "熊本高専前",
                "再春医療センター前",
                "御代志",
                "黒髪町",
                "藤崎宮前",
            ],
            [
                ("韓々坂", [210]),
                ("池田", [210, 210]),
                ("打越", [230, 210, 210]),
                ("坪井川公園", [230, 210, 210, 210]),
                ("北熊本", [280, 230, 210, 210, 210]),
                ("亀井", [350, 280, 280, 230, 210, 210]),
                ("八景水谷", [350, 350, 280, 230, 210, 210, 210]),
                ("堀川", [390, 390, 350, 280, 230, 230, 210, 210]),
                ("新須屋", [420, 420, 390, 350, 280, 280, 230, 230, 210]),
                ("須屋", [480, 420, 390, 390, 350, 280, 230, 280, 210, 210]),
                ("三ツ石", [540, 480, 420, 420, 350, 350, 280, 280, 230, 210, 210]),
                ("黒石", [540, 540, 480, 480, 390, 390, 350, 350, 280, 230, 210, 210]),
                ("熊本高専前", [550, 550, 540, 540, 420, 420, 390, 390, 280, 230, 210, 210, 210]),
                ("再春医療センター前", [560, 550, 540, 540, 480, 420, 390, 390, 350, 280, 230, 210, 210, 210]),
                ("御代志", [560, 550, 550, 540, 480, 480, 390, 390, 350, 280, 230, 210, 210, 210, 210]),
                ("黒髪町", [350, 280, 280, 230, 210, 210, 230, 230, 280, 350, 390, 390, 420, 480, 480, 540]),
                ("藤崎宮前", [390, 350, 350, 280, 280, 230, 280, 280, 350, 390, 420, 480, 480, 540, 550, 550, 210]),
            ],
        ),
    },
    {
        "key": "hieizan_railway_sakamoto_cable_station_pairs_202604",
        "operatorIds": ["比叡山鉄道"],
        "operatorName": "比叡山鉄道",
        "url": "https://sakamoto-cable.jp/guide/",
        "notes": [
            "比叡山鉄道公式の時刻表・運賃ページに掲載された坂本ケーブルの大人片道運賃960円を収録。往復運賃、回数券、定期券、団体割引、障がい者割引、小児運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_A7608498447722"],
        "pairs": station_pair_triangle_rows(
            ["ケーブル坂本", "ほうらい丘", "もたて山", "ケーブル延暦寺"],
            [
                ("ほうらい丘", [960]),
                ("もたて山", [960, 960]),
                ("ケーブル延暦寺", [960, 960, 960]),
            ],
        ),
    },
    {
        "key": "hokuriku_railroad_station_pairs_202501",
        "operatorIds": ["北陸鉄道"],
        "operatorName": "北陸鉄道",
        "url": "https://www.hokutetsu.co.jp/railway",
        "notes": [
            "北陸鉄道公式の鉄道線運賃ページに掲載された浅野川線・石川線の普通運賃画像から、大人普通運賃だけを転記。小児運賃、通勤・通学定期、障がい者割引、団体・企画券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_16E3E6C22CD178", "V4_ROUTE_5BCD7070D1A108"],
        "pairs": [
            *station_pair_triangle_rows(
                ["北鉄金沢", "七ツ屋", "上諸江", "磯部", "割出", "三口", "三ツ屋", "大河端", "北間", "蚊爪", "粟ヶ崎", "内灘"],
                [
                    ("七ツ屋", [200]),
                    ("上諸江", [200, 200]),
                    ("磯部", [230, 200, 200]),
                    ("割出", [230, 230, 200, 200]),
                    ("三口", [240, 230, 200, 200, 200]),
                    ("三ツ屋", [240, 240, 230, 200, 200, 200]),
                    ("大河端", [320, 290, 290, 290, 200, 200, 200]),
                    ("北間", [320, 320, 290, 290, 290, 200, 200, 200]),
                    ("蚊爪", [320, 320, 290, 290, 290, 290, 200, 200, 200]),
                    ("粟ヶ崎", [400, 370, 370, 370, 290, 290, 290, 200, 200, 200]),
                    ("内灘", [400, 400, 370, 370, 290, 290, 290, 290, 200, 200, 200]),
                ],
            ),
            *station_pair_triangle_rows(
                [
                    "野町",
                    "西泉",
                    "新西金沢",
                    "押野",
                    "野々市",
                    "野々市工大前",
                    "馬替",
                    "額住宅前",
                    "乙丸",
                    "四十万",
                    "陽羽里",
                    "曽谷",
                    "道法寺",
                    "井口",
                    "小柳",
                    "日御子",
                    "鶴来",
                ],
                [
                    ("西泉", [200]),
                    ("新西金沢", [210, 200]),
                    ("押野", [240, 230, 200]),
                    ("野々市", [240, 230, 200, 200]),
                    ("野々市工大前", [310, 290, 290, 200, 200]),
                    ("馬替", [320, 320, 290, 290, 200, 200]),
                    ("額住宅前", [400, 370, 290, 290, 290, 200, 200]),
                    ("乙丸", [400, 370, 370, 290, 290, 290, 200, 200]),
                    ("四十万", [440, 440, 440, 370, 370, 290, 290, 290, 200]),
                    ("陽羽里", [460, 440, 440, 370, 370, 370, 290, 290, 200, 200]),
                    ("曽谷", [460, 460, 440, 370, 370, 370, 290, 290, 290, 200, 200]),
                    ("道法寺", [460, 460, 440, 440, 370, 370, 370, 290, 290, 200, 200, 200]),
                    ("井口", [500, 490, 490, 440, 440, 440, 370, 370, 290, 290, 200, 200, 200]),
                    ("小柳", [500, 500, 490, 440, 440, 440, 370, 370, 370, 290, 290, 290, 200, 200]),
                    ("日御子", [540, 540, 490, 490, 490, 440, 440, 370, 370, 290, 290, 290, 290, 200, 200]),
                    ("鶴来", [540, 540, 540, 540, 490, 490, 490, 440, 440, 370, 370, 370, 290, 290, 290, 200]),
                ],
            ),
        ],
    },
    {
        "key": "asa_coast_railway_station_pairs_202403",
        "operatorIds": ["阿佐海岸鉄道"],
        "operatorName": "阿佐海岸鉄道",
        "url": "https://asatetu.com/fee/",
        "notes": [
            "阿佐海岸鉄道公式の2024年3月12日掲載・平日ルート運賃画像から、阿波海南駅・海部駅・宍喰駅・甲浦駅相互の上段大人運賃だけを転記。阿波海南文化村、海の駅東洋町、道の駅宍喰温泉などの道路区間停留所、小児運賃、障がい者割引、回数券、定期券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_0D3D97E8936C8A"],
        "pairs": station_pair_triangle_rows(
            ["阿波海南", "海部", "宍喰", "甲浦"],
            [
                ("海部", [200]),
                ("宍喰", [400, 300]),
                ("甲浦", [500, 400, 200]),
            ],
        ),
    },
    {
        "key": "fujisanroku_kawaguchiko_station_pairs_201404",
        "operatorIds": ["富士山麓電気鉄道"],
        "operatorName": "富士山麓電気鉄道",
        "url": "https://www.fujikyu-railway.jp/common/images/tickets/pdf/260401teikigai.pdf",
        "notes": [
            "富士山麓電気鉄道公式の富士急行線電車旅客運賃表（平成26年4月1日改正）から、ゲーム側で社線内だけになっている河口湖線3駅の上段大人普通運賃だけを転記。大月線側は現在のゲーム route にJR中央線・総武線が混在しているため未収録。小児運賃、特急料金、富士回遊のJR連絡運賃、企画券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_83E0CFBC2D3044"],
        "pairs": station_pair_triangle_rows(
            ["富士山", "富士急ハイランド", "河口湖"],
            [
                ("富士急ハイランド", [170]),
                ("河口湖", [220, 170]),
            ],
        ),
    },
    {
        "key": "fujisanroku_otsuki_line_station_pairs_201404",
        "operatorIds": ["富士山麓電気鉄道"],
        "operatorName": "富士山麓電気鉄道",
        "url": "https://www.fujikyu-railway.jp/common/images/tickets/pdf/260401teikigai.pdf",
        "notes": [
            "富士急行線電車旅客運賃表（平成26年4月1日改正）の普通旅客運賃から、大月-河口湖間の大人普通運賃を転記。",
            "ゲーム側の大月線 route にはJR中央線・総武線の駅が混在しているため、この表は富士山麓電気鉄道線内だけを覆い、JR区間は複合運賃解決に委ねる。",
            "小児運賃、特急料金、富士回遊のJR連絡運賃、企画券は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_894BB4712F3B4F"],
        "pairs": station_pair_upper_triangle_rows(
            [
                "大月",
                "上大月",
                "田野倉",
                "禾生",
                "赤坂",
                "都留市",
                "谷村町",
                "都留文科大学前",
                "十日市場",
                "東桂",
                "三つ峠",
                "寿",
                "葭池温泉前",
                "下吉田",
                "月江寺",
                "富士山",
                "富士急ハイランド",
                "河口湖",
            ],
            [
                ("大月", [170, 220, 300, 380, 460, 460, 550, 550, 630, 710, 870, 960, 960, 960, 1020, 1080, 1140]),
                ("上大月", [220, 300, 380, 380, 460, 460, 550, 630, 710, 870, 870, 960, 960, 1020, 1080, 1080]),
                ("田野倉", [220, 300, 300, 380, 380, 460, 550, 630, 710, 790, 870, 870, 960, 960, 1020]),
                ("禾生", [170, 220, 220, 300, 300, 380, 550, 630, 710, 710, 790, 790, 870, 960]),
                ("赤坂", [170, 220, 220, 300, 300, 460, 550, 630, 630, 710, 790, 790, 870]),
                ("都留市", [170, 170, 220, 300, 380, 550, 550, 630, 630, 710, 790, 790]),
                ("谷村町", [170, 220, 220, 380, 460, 550, 550, 630, 710, 710, 790]),
                ("都留文科大学前", [170, 220, 300, 460, 460, 550, 550, 630, 710, 710]),
                ("十日市場", [170, 300, 380, 460, 460, 550, 630, 630, 710]),
                ("東桂", [220, 300, 380, 380, 460, 550, 550, 630]),
                ("三つ峠", [220, 300, 300, 380, 380, 460, 550]),
                ("寿", [170, 220, 220, 300, 380, 380]),
                ("葭池温泉前", [170, 170, 220, 300, 380]),
                ("下吉田", [170, 220, 220, 300]),
                ("月江寺", [170, 220, 300]),
                ("富士山", [170, 220]),
                ("富士急ハイランド", [170]),
            ],
        ),
    },
    {
        "key": "tateyama_kurobe_cable_station_pairs_202604",
        "operatorIds": ["立山黒部貫光"],
        "operatorName": "立山黒部貫光",
        "url": "https://www.alpen-route.com/access_new/fare/person/route_data.json",
        "notes": [
            "立山黒部アルペンルート公式運賃検索データ（2026年4月15日以降適用）から、鋼索線としてゲームに存在する立山-美女平と黒部平-黒部湖の大人片道運賃だけを収録。",
            "現在のゲーム側 route は離れた2つの鋼索鉄道区間を同一routeIdに束ねているため、美女平-黒部平など途中の高原バス・トロリーバス・ロープウェイ区間はこの鉄道運賃表では覆わない。",
            "小児運賃、往復割引、団体、障害者割引、バス、ロープウェイ、電鉄富山・扇沢・長野方面の連絡運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_B2DB73B58E1C85"],
        "pairs": [
            ("立山", "美女平", 1090),
            ("黒部平", "黒部湖", 1150),
        ],
    },
    {
        "key": "nankai_airport_line_station_pairs_202504",
        "operatorIds": ["南海電気鉄道"],
        "operatorName": "南海電気鉄道",
        "url": "https://www.nankai.co.jp/lib/company/handbook/pdf/handbook2025.pdf",
        "notes": [
            "南海電気鉄道2025ハンドブックの2025年4月1日改定普通旅客運賃表から、空港線内の大人普通運賃を収録。泉佐野-りんくうタウンは南海線対キロ運賃に空港線加算130円を加算、泉佐野-関西空港は空港線加算230円を加算、りんくうタウン-関西空港は公式特定運賃370円を使用。小児運賃、特急料金、特別車両料金は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_770122636049D3"],
        "pairs": [
            ("泉佐野", "りんくうタウン", 310),
            ("泉佐野", "関西空港", 520),
            ("りんくうタウン", "関西空港", 370),
        ],
    },
    {
        "key": "nankai_koyasan_cable_station_pairs_202504",
        "operatorIds": ["南海電気鉄道"],
        "operatorName": "南海電気鉄道",
        "url": "https://www.nankai.co.jp/lib/company/handbook/pdf/handbook2025.pdf",
        "notes": [
            "南海電気鉄道2025ハンドブックの鋼索線（高野山ケーブルカー）均一制普通旅客運賃から、大人普通運賃500円を収録。小児運賃および鉄道線との通算乗車時の合算処理は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_B3A1329704DCFE"],
        "pairs": [("極楽橋", "高野山", 500)],
    },
    {
        "key": "odakyu_hakone_cable_station_pairs_202210",
        "operatorIds": ["小田急箱根"],
        "operatorName": "小田急箱根",
        "url": "https://www.hakonenavi.jp/assets/file/hakone-tozan_fee_221001.pdf",
        "notes": [
            "小田急箱根（箱根登山鉄道）公式の2022年10月1日改定・普通旅客運賃表から、鋼索線（箱根登山ケーブルカー）内の大人普通運賃だけを転記。鉄道線、小児運賃、団体割引、特急券、フリーパス類は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_EA2933F3255769"],
        "pairs": station_pair_triangle_rows(
            ["強羅", "公園下", "公園上", "中強羅", "上強羅", "早雲山"],
            [
                ("公園下", [90]),
                ("公園上", [170, 90]),
                ("中強羅", [250, 170, 90]),
                ("上強羅", [340, 250, 170, 90]),
                ("早雲山", [430, 340, 250, 170, 90]),
            ],
        ),
    },
    {
        "key": "tkj_johoku_line_station_pairs_2026",
        "operatorIds": ["jr東海交通事業"],
        "operatorName": "JR東海交通事業",
        "url": "https://tkj-i.co.jp/timetable/",
        "notes": [
            "JR東海交通事業公式の城北線各駅運賃表画像から、大人普通運賃だけを転記。小児運賃、回数券、定期券、JR線連絡運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_61AFEBA48292E6"],
        "pairs": station_pair_triangle_rows(
            ["枇杷島", "尾張星の宮", "小田井", "比良", "味美", "勝川"],
            [
                ("尾張星の宮", [230]),
                ("小田井", [320, 230]),
                ("比良", [390, 320, 230]),
                ("味美", [450, 390, 320, 230]),
                ("勝川", [450, 450, 390, 320, 230]),
            ],
        ),
    },
    {
        "key": "yokkaichi_asunarou_station_pairs_201910",
        "operatorIds": ["四日市あすなろう鉄道"],
        "operatorName": "四日市あすなろう鉄道",
        "url": "https://yar.co.jp/imgdata/202408071638181.pdf",
        "notes": [
            "四日市あすなろう鉄道公式の普通旅客運賃表（2019年10月改定）から、大人普通運賃の三角表を転記。上段の大人運賃のみを収録し、下段の小児運賃、定期券、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_702A48945EFB6B", "V4_ROUTE_CF49068E0D09DC"],
        "pairs": station_pair_triangle_rows(
            ["あすなろう四日市", "赤堀", "日永", "南日永", "泊", "追分", "小古曽", "内部", "西日野"],
            [
                ("赤堀", [200]),
                ("日永", [200, 200]),
                ("南日永", [200, 200, 200]),
                ("泊", [270, 200, 200, 200]),
                ("追分", [270, 270, 200, 200, 200]),
                ("小古曽", [270, 270, 270, 200, 200, 200]),
                ("内部", [270, 270, 270, 270, 200, 200, 200]),
                ("西日野", [270, 200, 200, 200, 270, 270, 270, 270]),
            ],
        ),
    },
    {
        "key": "keihan_iwashimizu_cable_station_pairs_2026",
        "operatorIds": ["京阪電気鉄道"],
        "operatorName": "京阪電気鉄道",
        "url": "https://www.keihan.co.jp/traffic/time-fare/iwashimizu.html",
        "notes": [
            "京阪公式の石清水八幡宮参道ケーブル運賃・時刻表に掲載された大人片道普通運賃。往復、小児、定期運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_D6C48165646C89"],
        "pairs": [("ケーブル八幡宮口", "ケーブル八幡宮山上", 300)],
    },
    {
        "key": "kobe_subway_hokushin_station_pairs_202006",
        "operatorIds": ["神戸市"],
        "operatorName": "神戸市交通局",
        "url": "https://kotsu.city.kobe.lg.jp/subway/ryokin-teiki/kukansu-kyori/hokushin/",
        "notes": [
            "神戸市交通局公式の北神線（谷上-新神戸）地下鉄料金表に掲載された大人普通料金。小児、障害者割引、回数、定期料金は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_EEB52C003BB0C5"],
        "pairs": [("谷上", "新神戸", 280)],
    },
    {
        "key": "yakuri_cable_station_pairs_2026",
        "operatorIds": ["四国ケブル"],
        "operatorName": "四国ケーブル",
        "url": "https://www.shikoku-cable.co.jp/yakuri/price/",
        "notes": [
            "四国ケーブル公式の八栗ケーブル普通運賃。大人片道は上り（八栗登山口→八栗山上）600円、下り（八栗山上→八栗登山口）500円の方向別運賃として収録。往復、小学生、団体、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_6D177612D76A98"],
        "pairs": [
            ("八栗登山口", "八栗山上", 600),
            ("八栗山上", "八栗登山口", 500),
        ],
    },
    {
        "key": "kuramadera_cable_station_pairs_2026",
        "operatorIds": ["鞍馬寺"],
        "operatorName": "鞍馬寺",
        "url": "https://www.kuramadera.or.jp/access.html",
        "notes": [
            "鞍馬寺公式のケーブルコース案内に掲載されたケーブル寄付金（大人・片道200円）を、山門-多宝塔間の片道相当運賃として収録。小学生以下、愛山費、徒歩コースは別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_BD8424D09C8D45"],
        "pairs": [("山門", "多宝塔", 200)],
    },
    {
        "key": "choshi_dentetsu_station_pairs_201910",
        "operatorIds": ["銚子電気鉄道"],
        "operatorName": "銚子電気鉄道",
        "url": "https://www.choshi-dentetsu.jp/wp-content/uploads/2024/12/fare2019.jpg",
        "notes": [
            "銚子電気鉄道公式の普通旅客運賃表（令和元年10月1日改定）から、大人普通運賃の三角表を転記。小児運賃、一日乗車券、割引運賃は別体系のため未収録。",
        ],
        "routeIds": ["V4_ROUTE_C0852E06ADC6AE"],
        "pairs": station_pair_triangle_rows(
            ["銚子", "仲ノ町", "観音", "本銚子", "笠上黒生", "西海鹿島", "海鹿島", "君ヶ浜", "犬吠", "外川"],
            [
                ("仲ノ町", [180]),
                ("観音", [210, 180]),
                ("本銚子", [210, 210, 180]),
                ("笠上黒生", [240, 240, 210, 180]),
                ("西海鹿島", [270, 240, 240, 210, 180]),
                ("海鹿島", [270, 270, 240, 210, 180, 180]),
                ("君ヶ浜", [300, 300, 270, 240, 210, 210, 210]),
                ("犬吠", [350, 300, 300, 270, 240, 240, 210, 180]),
                ("外川", [350, 350, 350, 300, 270, 270, 240, 210, 180]),
            ],
        ),
    },
    {
        "key": "toyohashi_atsumi_station_pairs_202403",
        "operatorIds": ["豊橋鉄道"],
        "operatorName": "豊橋鉄道",
        "url": "https://www.toyotetsu.com/ufile/library/2022_file.pdf",
        "notes": [
            "豊橋鉄道公式の鉄軌道事業旅客運賃改定資料に掲載された2024年春改定後の渥美線普通旅客運賃。既存の駅間表に対して公式資料どおり全区間30円加算した大人普通運賃だけを収録。",
        ],
        "routeIds": ["V4_ROUTE_4D89F60D3DB058"],
        "pairs": station_pair_triangle_rows(
            ["新豊橋", "柳生橋", "小池", "愛知大学前", "南栄", "高師", "芦原", "植田", "向ヶ丘", "大清水", "老津", "杉山", "やぐま台", "神戸", "豊島", "三河田原"],
            [
                ("柳生橋", [170]),
                ("小池", [170, 170]),
                ("愛知大学前", [170, 170, 170]),
                ("南栄", [170, 170, 170, 170]),
                ("高師", [170, 170, 170, 170, 200]),
                ("芦原", [170, 170, 170, 170, 200, 220]),
                ("植田", [170, 170, 170, 170, 200, 220, 250]),
                ("向ヶ丘", [170, 170, 170, 170, 200, 220, 250, 280]),
                ("大清水", [170, 170, 170, 200, 220, 220, 250, 280, 310]),
                ("老津", [170, 170, 200, 220, 250, 280, 310, 310, 340, 370]),
                ("杉山", [170, 200, 220, 250, 280, 310, 340, 370, 370, 400, 420]),
                ("やぐま台", [170, 170, 220, 250, 280, 310, 340, 370, 400, 420, 420, 450]),
                ("神戸", [170, 170, 200, 280, 310, 340, 370, 400, 420, 450, 450, 480, 500]),
                ("豊島", [170, 170, 200, 250, 310, 340, 370, 400, 420, 450, 480, 500, 530, 550]),
                ("三河田原", [170, 170, 170, 220, 280, 340, 370, 400, 420, 450, 480, 500, 530, 530, 550]),
            ],
        ),
    },
    {
        "key": "toyohashi_city_line_station_pairs_202403",
        "operatorIds": ["豊橋鉄道"],
        "operatorName": "豊橋鉄道",
        "url": "https://www.toyotetsu.com/shinaisen/charges.html",
        "notes": [
            "豊橋鉄道公式の市内線運賃・定期券ページに掲載された全線一律の片道大人普通運賃（200円）を、全停留場間の駅間表として収録。",
        ],
        "routeIds": ["V4_ROUTE_84FDC3869098B6"],
        "pairs": station_pair_flat_rows(
            ["駅前", "駅前大通", "新川", "札木", "市役所前", "豊橋公園前", "東八町", "前畑", "東田坂上", "東田", "競輪場前", "井原", "赤岩口", "運動公園前"],
            200,
        ),
    },
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
        "key": "donan_isaribi_station_pairs_202504",
        "operatorIds": ["道南いさりび鉄道"],
        "operatorName": "道南いさりび鉄道",
        "url": "https://www.shr-isaribi.jp/wp-content/uploads/2024/11/91dc7bfd1306995f002d94f66baf906a.pdf",
        "notes": [
            "道南いさりび鉄道公式の2025年4月1日改定普通乗車券（片道）運賃表から、会社線内（五稜郭-木古内）の大人普通運賃だけを転記。JR函館連絡運賃は別体系のため未適用。",
        ],
        "routeIds": ["V4_ROUTE_B261CE61DC4849"],
        "pairs": station_pair_triangle_rows(
            ["五稜郭", "七重浜", "東久根別", "久根別", "清川口", "上磯", "茂辺地", "渡島当別", "釜谷", "泉沢", "札苅", "木古内"],
            [
                ("七重浜", [250]),
                ("東久根別", [290, 250]),
                ("久根別", [290, 250, 210]),
                ("清川口", [340, 250, 250, 210]),
                ("上磯", [340, 290, 250, 250, 210]),
                ("茂辺地", [530, 380, 380, 380, 340, 340]),
                ("渡島当別", [660, 530, 530, 530, 380, 380, 250]),
                ("釜谷", [790, 790, 660, 660, 530, 530, 340, 250]),
                ("泉沢", [930, 790, 790, 790, 660, 660, 380, 340, 250]),
                ("札苅", [1080, 930, 930, 790, 790, 790, 530, 380, 290, 250]),
                ("木古内", [1080, 1080, 1080, 930, 930, 930, 660, 530, 380, 340, 250]),
            ],
        ),
    },
    {
        "key": "shigaraki_kogen_station_pairs",
        "operatorIds": ["信楽高原鐵道"],
        "operatorName": "信楽高原鐵道",
        "url": "https://skr.mi-ktt.ne.jp/fare/",
        "notes": [
            "信楽高原鐵道公式サイトの普通運賃表から大人普通運賃の三角表を転記。",
        ],
        "routeIds": ["V4_ROUTE_0E1E07593BCF5F"],
        "pairs": station_pair_triangle_rows(
            ["貴生川", "紫香楽宮跡", "雲井", "勅旨", "玉桂寺前", "信楽"],
            [
                ("紫香楽宮跡", [410]),
                ("雲井", [410, 210]),
                ("勅旨", [470, 210, 210]),
                ("玉桂寺前", [470, 290, 290, 210]),
                ("信楽", [470, 290, 290, 210, 210]),
            ],
        ),
    },
    {
        "key": "tsugaru_railway_station_pairs_201910",
        "operatorIds": ["津軽鉄道"],
        "operatorName": "津軽鉄道",
        "url": "https://tsutetsu.com/tsutetsu/wp-content/uploads/2019/09/bd33ac23bf812b51340f61666c16239c.pdf",
        "notes": [
            "津軽鉄道公式の2019年10月1日改定普通旅客運賃表PDFから大人普通運賃の三角表を転記。公式表の五所川原表記は、ゲーム側の駅名に合わせて津軽五所川原として収録。",
            "ストーブ列車券などの追加料金は普通運賃とは別料金のため未適用。",
        ],
        "routeIds": ["V4_ROUTE_352F9474B712C9"],
        "pairs": station_pair_triangle_rows(
            ["津軽五所川原", "十川", "五農校前", "津軽飯詰", "毘沙門", "嘉瀬", "金木", "芦野公園", "川倉", "大沢内", "深郷田", "津軽中里"],
            [
                ("十川", [180]),
                ("五農校前", [210, 180]),
                ("津軽飯詰", [260, 180, 180]),
                ("毘沙門", [400, 360, 260, 210]),
                ("嘉瀬", [490, 430, 360, 310, 180]),
                ("金木", [560, 520, 460, 430, 310, 180]),
                ("芦野公園", [650, 560, 520, 490, 360, 260, 180]),
                ("川倉", [690, 650, 560, 520, 430, 310, 210, 180]),
                ("大沢内", [770, 730, 650, 610, 490, 400, 260, 210, 180]),
                ("深郷田", [800, 770, 690, 650, 520, 430, 360, 260, 180, 180]),
                ("津軽中里", [870, 840, 770, 730, 610, 490, 400, 360, 260, 180, 180]),
            ],
        ),
    },
    {
        "key": "aketetsu_station_pairs_201910",
        "operatorIds": ["明知鉄道"],
        "operatorName": "明知鉄道",
        "url": "https://www.aketetsu.co.jp/fare/",
        "notes": [
            "明知鉄道公式サイトの2019年10月1日改正通常運賃表から、大人普通運賃の三角表を転記。",
        ],
        "routeIds": ["V4_ROUTE_6B62C0A030B7FC"],
        "pairs": station_pair_triangle_rows(
            ["恵那", "東野", "飯沼", "阿木", "飯羽間", "極楽", "岩村", "花白温泉", "山岡", "野志", "明智"],
            [
                ("東野", [200]),
                ("飯沼", [220, 270]),
                ("阿木", [200, 270, 320]),
                ("飯羽間", [200, 220, 370, 440]),
                ("極楽", [200, 220, 270, 370, 440]),
                ("岩村", [200, 200, 220, 270, 440, 490]),
                ("花白温泉", [220, 220, 220, 320, 370, 490, 580]),
                ("山岡", [200, 220, 220, 270, 320, 440, 530, 580]),
                ("野志", [220, 220, 320, 320, 370, 440, 490, 620, 650]),
                ("明智", [200, 220, 270, 370, 370, 440, 490, 530, 650, 690]),
            ],
        ),
    },
    {
        "key": "shibayama_railway_station_pairs_202403",
        "operatorIds": ["芝山鉄道"],
        "operatorName": "芝山鉄道",
        "url": "https://www.sibatetu.co.jp/schedule.html",
        "notes": [
            "芝山鉄道公式サイトの2024年3月16日改正・芝山千代田駅からの普通運賃表。芝山鉄道線内の大人普通運賃を転記。",
        ],
        "routeIds": ["V4_ROUTE_5386B87741F27E"],
        "pairs": [
            ("東成田", "芝山千代田", 220),
        ],
    },
    {
        "key": "hojo_railway_station_pairs_202407",
        "operatorIds": ["北条鉄道"],
        "operatorName": "北条鉄道",
        "url": "https://kasaipublictrans.jp/public-transport/hojo-train/",
        "notes": [
            "加西市公共交通ポータルNAVIGOかさい掲載の北条鉄道大人運賃表画像（2024年7月掲載）から、北条線内の大人普通運賃を転記。",
        ],
        "routeIds": ["V4_ROUTE_83652696DA1295"],
        "pairs": station_pair_triangle_rows(
            ["北条町", "播磨横田", "長", "播磨下里", "法華口", "田原", "網引", "粟生"],
            [
                ("播磨横田", [210]),
                ("長", [210, 160]),
                ("播磨下里", [260, 210, 160]),
                ("法華口", [310, 260, 210, 160]),
                ("田原", [360, 310, 260, 210, 160]),
                ("網引", [390, 310, 310, 260, 210, 160]),
                ("粟生", [420, 390, 360, 310, 310, 260, 210]),
            ],
        ),
    },
    {
        "key": "kominato_railway_station_pairs_201910",
        "operatorIds": ["小湊鐵道"],
        "operatorName": "小湊鐵道",
        "url": "https://www.kominato.co.jp/wp-content/uploads/tickets/faretable.pdf",
        "notes": [
            "小湊鐵道公式の旅客運賃表PDF（令和元年10月1日改定）から、上段の大人片道普通運賃だけを転記。下段の往復割引運賃は別制度のため未適用。",
        ],
        "routeIds": ["V4_ROUTE_E6B8542C55C2AA"],
        "pairs": station_pair_triangle_rows(
            [
                "五井",
                "上総村上",
                "海士有木",
                "上総三又",
                "上総山田",
                "光風台",
                "馬立",
                "上総牛久",
                "上総川間",
                "上総鶴舞",
                "上総久保",
                "高滝",
                "里見",
                "飯給",
                "月崎",
                "上総大久保",
                "養老渓谷",
                "上総中野",
            ],
            [
                ("上総村上", [140]),
                ("海士有木", [250, 140]),
                ("上総三又", [340, 210, 140]),
                ("上総山田", [380, 290, 170, 140]),
                ("光風台", [460, 380, 250, 170, 140]),
                ("馬立", [540, 420, 290, 250, 170, 140]),
                ("上総牛久", [710, 590, 460, 420, 340, 250, 170]),
                ("上総川間", [780, 670, 590, 500, 420, 340, 290, 140]),
                ("上総鶴舞", [810, 740, 630, 540, 500, 420, 340, 170, 140]),
                ("上総久保", [870, 810, 710, 630, 590, 500, 420, 250, 170, 140]),
                ("高滝", [930, 870, 780, 710, 670, 590, 500, 340, 250, 170, 140]),
                ("里見", [1000, 930, 840, 780, 740, 670, 590, 420, 340, 250, 170, 140]),
                ("飯給", [1060, 960, 900, 840, 780, 710, 670, 500, 380, 340, 250, 170, 140]),
                ("月崎", [1120, 1060, 960, 900, 870, 810, 740, 590, 500, 420, 340, 250, 210, 140]),
                ("上総大久保", [1220, 1120, 1030, 1000, 930, 870, 810, 670, 590, 540, 460, 380, 290, 210, 140]),
                ("養老渓谷", [1280, 1220, 1120, 1060, 1030, 960, 900, 780, 710, 630, 540, 500, 420, 340, 250, 140]),
                ("上総中野", [1440, 1340, 1250, 1180, 1150, 1090, 1030, 900, 840, 810, 740, 670, 590, 500, 420, 290, 210]),
            ],
        ),
    },
    {
        "key": "tarumi_railway_station_pairs_201910",
        "operatorIds": ["樽見鉄道"],
        "operatorName": "樽見鉄道",
        "url": "https://tarumi-railway.com/pdf/fare/file/1",
        "notes": [
            "樽見鉄道公式の旅客運賃表PDF（2019年10月1日改定）から、大人普通運賃の三角表を転記。",
        ],
        "routeIds": ["V4_ROUTE_68672E83484228"],
        "pairs": station_pair_triangle_rows(
            [
                "大垣",
                "東大垣",
                "横屋",
                "十九条",
                "美江寺",
                "北方真桑",
                "モレラ岐阜",
                "糸貫",
                "本巣",
                "織部",
                "木知原",
                "谷汲口",
                "神海",
                "高科",
                "鍋原",
                "日当",
                "高尾",
                "水鳥",
                "樽見",
            ],
            [
                ("東大垣", [190]),
                ("横屋", [260, 190]),
                ("十九条", [260, 190, 190]),
                ("美江寺", [320, 260, 190, 190]),
                ("北方真桑", [390, 320, 320, 260, 260]),
                ("モレラ岐阜", [460, 390, 320, 320, 260, 190]),
                ("糸貫", [460, 390, 320, 320, 260, 190, 190]),
                ("本巣", [530, 460, 390, 390, 320, 260, 260, 190]),
                ("織部", [530, 460, 460, 390, 390, 320, 260, 260, 190]),
                ("木知原", [600, 530, 530, 460, 460, 390, 320, 320, 260, 190]),
                ("谷汲口", [680, 600, 530, 530, 460, 390, 390, 320, 260, 260, 190]),
                ("神海", [680, 600, 600, 600, 530, 460, 390, 390, 320, 320, 260, 190]),
                ("高科", [750, 680, 600, 600, 530, 460, 460, 390, 320, 320, 260, 260, 190]),
                ("鍋原", [750, 680, 680, 600, 600, 530, 460, 460, 390, 320, 320, 260, 190, 190]),
                ("日当", [820, 750, 680, 680, 600, 530, 530, 460, 460, 390, 320, 320, 260, 260, 190]),
                ("高尾", [900, 820, 750, 750, 680, 600, 530, 530, 460, 460, 390, 320, 320, 260, 260, 190]),
                ("水鳥", [900, 820, 820, 750, 750, 680, 600, 600, 530, 460, 460, 390, 320, 320, 320, 260, 190]),
                ("樽見", [930, 900, 820, 820, 750, 680, 680, 680, 600, 530, 460, 460, 390, 390, 320, 320, 260, 190]),
            ],
        ),
    },
    {
        "key": "mizushima_rinkai_station_pairs_201910",
        "operatorIds": ["水島臨海鉄道"],
        "operatorName": "水島臨海鉄道",
        "url": "https://www.mizurin.co.jp/mzsm-admin-page/upload_images/service/uploads_dir2/1567670351-system_5d70c04fea685.pdf",
        "notes": [
            "水島臨海鉄道公式の運賃・料金表PDF（2019年10月1日改定）から、水島本線内の大人普通運賃を転記。",
        ],
        "routeIds": ["V4_ROUTE_A2FFEE5E87B424"],
        "pairs": station_pair_triangle_rows(
            ["倉敷市", "球場前", "西富井", "福井", "浦田", "弥生", "栄", "常盤", "水島", "三菱自工前"],
            [
                ("球場前", [190]),
                ("西富井", [250, 190]),
                ("福井", [250, 190, 190]),
                ("浦田", [250, 190, 190, 190]),
                ("弥生", [250, 190, 190, 190, 190]),
                ("栄", [330, 250, 190, 190, 190, 190]),
                ("常盤", [330, 250, 250, 190, 190, 190, 190]),
                ("水島", [330, 330, 250, 190, 190, 190, 190, 190]),
                ("三菱自工前", [350, 330, 250, 250, 250, 190, 190, 190, 190]),
            ],
        ),
    },
    {
        "key": "yuri_kogen_station_pairs_201910",
        "operatorIds": ["由利高原鉄道"],
        "operatorName": "由利高原鉄道",
        "url": "https://www.obako5.com/wp-content/uploads/2019/09/0e470b007849bb4e8cf46ad62ab865b8.pdf",
        "notes": [
            "由利高原鉄道公式の鳥海山ろく線「おばこ号」運賃表PDF（2019年10月1日改正）から、大人普通運賃の三角表を転記。",
        ],
        "routeIds": ["V4_ROUTE_0B8209CD66440A"],
        "pairs": station_pair_triangle_rows(
            ["羽後本荘", "薬師堂", "子吉", "鮎川", "黒沢", "曲沢", "前郷", "久保田", "西滝沢", "吉沢", "川辺", "矢島"],
            [
                ("薬師堂", [180]),
                ("子吉", [250, 180]),
                ("鮎川", [330, 250, 180]),
                ("黒沢", [400, 330, 250, 180]),
                ("曲沢", [400, 330, 250, 180, 180]),
                ("前郷", [400, 400, 330, 250, 180, 180]),
                ("久保田", [460, 400, 400, 330, 250, 250, 180]),
                ("西滝沢", [510, 460, 400, 330, 330, 250, 250, 180]),
                ("吉沢", [510, 460, 460, 400, 330, 330, 250, 250, 180]),
                ("川辺", [560, 510, 510, 460, 400, 400, 330, 330, 250, 180]),
                ("矢島", [610, 560, 560, 510, 460, 460, 400, 400, 330, 250, 180]),
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
    cache_path = cache_dir / (cache_stem_for_url(url) + ".html")
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
    cache_path = cache_dir / (cache_stem_for_url(url) + ".html")
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
    cache_path = cache_dir / (cache_stem_for_url(url) + ".pdf")
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


def fetch_pdf_raw_text(url: str, cache_dir: Path) -> tuple[str, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (cache_stem_for_url(url) + ".pdf")
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
    return str(cache_path.relative_to(ROOT)), completed.stdout


def fetch_pdf_xml_text_elements(url: str, cache_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (cache_stem_for_url(url) + ".pdf")
    if not cache_path.exists():
        response = requests.get(url, timeout=30, headers={"User-Agent": "OniChase fare rule collector/1.0"})
        response.raise_for_status()
        cache_path.write_bytes(response.content)
    with tempfile.TemporaryDirectory() as temp_dir:
        output_prefix = Path(temp_dir) / "pdf_xml"
        subprocess.run(
            ["pdftohtml", "-xml", "-f", "1", "-l", "1", str(cache_path), str(output_prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
        root = ET.parse(output_prefix.with_suffix(".xml")).getroot()
    elements: list[dict[str, Any]] = []
    for node in root.iter("text"):
        text = re.sub(r"\s+", " ", "".join(node.itertext())).strip()
        if not text:
            continue
        elements.append({
            "top": int(node.attrib.get("top", "0")),
            "left": int(node.attrib.get("left", "0")),
            "text": text,
        })
    return str(cache_path.relative_to(ROOT)), elements


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


def parse_nishikigawa_railway_pairs(
    lines: list[str],
    station_order: list[str],
) -> dict[str, dict[str, Any]]:
    station_names = set(station_order)
    pairs: dict[str, dict[str, Any]] = {}
    current_origin: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            line in station_names
            and index + 4 < len(lines)
            and lines[index + 1:index + 5] == ["駅名", "大人", "小人", "通勤定期（1ヶ月/3ヶ月/6ヶ月）"]
        ):
            current_origin = line
            index += 5
            continue
        if current_origin and line in station_names and index + 1 < len(lines) and lines[index + 1].endswith("円"):
            if line != current_origin:
                add_station_pair(pairs, current_origin, line, parse_first_money(lines[index + 1]))
            index += 2
            continue
        index += 1
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Nishikigawa Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_watarase_keikoku_pairs(
    lines: list[str],
    station_order: list[str],
) -> dict[str, dict[str, Any]]:
    station_names = set(station_order)
    pairs: dict[str, dict[str, Any]] = {}
    for origin_name in station_order:
        header = f"{origin_name}駅から"
        try:
            start = lines.index(header)
        except ValueError as error:
            raise ValueError(f"missing Watarase fare section for {origin_name}") from error
        index = start + 1
        while index < len(lines):
            line = lines[index]
            if line.endswith("駅から") and line != header:
                break
            if line in station_names:
                if index + 2 >= len(lines):
                    break
                adult_fare = lines[index + 1]
                if adult_fare != "-" and line != origin_name:
                    add_station_pair(pairs, origin_name, line, parse_first_money(adult_fare))
                index += 3
                continue
            index += 1
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Watarase Keikoku Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_joshin_dentetsu_page(
    origin_name: str,
    lines: list[str],
    station_order: list[str],
) -> dict[str, dict[str, Any]]:
    if origin_name not in station_order:
        raise ValueError(f"unknown Joshin origin station {origin_name!r}")
    try:
        start = lines.index("運賃")
    except ValueError:
        return {}
    end = lines.index("アクセス", start) if "アクセス" in lines[start:] else len(lines)
    table_lines = lines[start:end]
    pairs: dict[str, dict[str, Any]] = {}
    station_names = set(station_order)
    index = 0
    while index < len(table_lines) - 1:
        dest_name = table_lines[index]
        fare_text = table_lines[index + 1]
        if dest_name in station_names and fare_text.endswith("円"):
            if dest_name != origin_name:
                add_station_pair(pairs, origin_name, dest_name, parse_first_money(fare_text))
            index += 8
            continue
        index += 1
    return pairs


def parse_jomo_railway_pairs(html: str, station_order: list[str]) -> dict[str, dict[str, Any]]:
    label_matches = list(re.finditer(r'<label class="title"[^>]*>(.*?)</label>', html, re.S | re.I))
    station_names = set(station_order)
    pairs: dict[str, dict[str, Any]] = {}
    for label_index, label_match in enumerate(label_matches):
        origin_name = clean_html_table_cell(label_match.group(1)).removesuffix("駅")
        if origin_name not in station_names:
            continue
        block_end = label_matches[label_index + 1].start() if label_index + 1 < len(label_matches) else len(html)
        block = html[label_match.end():block_end]
        table_match = re.search(r"<table\b.*?</table>", block, re.S | re.I)
        if not table_match:
            raise ValueError(f"missing Jomo fare table for {origin_name}")
        for row_html in re.findall(r"<tr\b.*?</tr>", table_match.group(0), re.S | re.I):
            cells = [
                clean_html_table_cell(cell)
                for cell in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)
            ]
            if len(cells) < 2:
                continue
            dest_name, fare_text = cells[0], cells[1]
            if dest_name in station_names and fare_text.isdigit() and dest_name != origin_name:
                add_station_pair(pairs, origin_name, dest_name, int(fare_text))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Jomo Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_chichibu_railway_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    station_names = set(station_order)
    stations_by_length = sorted(station_order, key=len, reverse=True)
    current_origin: str | None = None
    pairs: dict[str, dict[str, Any]] = {}
    for line in lines:
        normalized_line = re.sub(r"\s+", "", line)
        if normalized_line in station_names:
            current_origin = normalized_line
            continue
        if current_origin is None:
            continue
        row_match = re.match(r"^\d+\.\d\s+(.+)$", line)
        if not row_match:
            continue
        row_body = re.sub(r"\s+", "", row_match.group(1))
        dest_name = next((station for station in stations_by_length if row_body.startswith(station)), None)
        values = re.findall(r"\d[\d,]*", line)
        if not dest_name or len(values) < 3:
            continue
        if dest_name != current_origin:
            add_station_pair(pairs, current_origin, dest_name, int(values[-2].replace(",", "")))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Chichibu Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_numbered_pdf_triangle_pairs(
    lines: list[str],
    station_order: list[str],
    *,
    source_name: str,
) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    for station_index, station_name in enumerate(station_order[1:], start=2):
        row_line = next(
            (
                line
                for line in lines
                if re.match(rf"^{station_index}\s", line) and station_name in line
            ),
            None,
        )
        if row_line is None:
            if station_name == "フルーツパーク":
                row_line = next((line for line in lines if re.match(rf"^{station_index}\s", line) and "パーク" in line), None)
            elif station_name == "浜名湖佐久米":
                row_line = next((line for line in lines if re.match(rf"^{station_index}\s", line)), None)
        if row_line is None:
            raise ValueError(f"missing {source_name} fare row for {station_index} {station_name}")
        values = [parse_first_money(value) for value in re.findall(r"\d[\d,]*", row_line)]
        if not values or values[0] != station_index:
            raise ValueError(f"unexpected {source_name} fare row prefix: {row_line}")
        fares = values[1:station_index]
        if len(fares) != station_index - 1:
            raise ValueError(f"{source_name} {station_name} fare row has {len(fares)} fares, expected {station_index - 1}")
        fare_rows.append((station_name, fares))
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"{source_name} pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_yoro_railway_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    for station_index, station_name in enumerate(station_order[1:], start=1):
        label_index = next((index for index, line in enumerate(lines) if line.strip() == station_name), None)
        if label_index is None or label_index == 0:
            raise ValueError(f"missing Yoro Railway fare row label for {station_name}")
        adult_line = lines[label_index - 1]
        fares = [parse_first_money(value) for value in re.findall(r"\d[\d,]*", adult_line)]
        if len(fares) != station_index:
            raise ValueError(f"Yoro Railway {station_name} fare row has {len(fares)} fares, expected {station_index}: {adult_line}")
        fare_rows.append((station_name, fares))
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Yoro Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_matsuura_railway_pairs(raw_text: str, station_order: list[str]) -> dict[str, dict[str, Any]]:
    pages = raw_text.split("\f")
    if len(pages) < 3:
        raise ValueError("Matsuura Railway fare PDF did not contain the expected 3 text pages")

    def page_fare_rows(page_text: str) -> list[list[int]]:
        rows: list[list[int]] = []
        for line in page_text.splitlines():
            line = line.split("令和", 1)[0]
            values = [
                int(value.lstrip("★").replace(",", ""))
                for value in re.findall(r"★?\d[\d,]*", line)
            ]
            if values:
                rows.append(values)
        return rows

    first_page_rows = page_fare_rows(pages[0])
    second_page_rows = page_fare_rows(pages[1])
    third_page_rows = page_fare_rows(pages[2])
    if [len(row) for row in first_page_rows] != list(range(1, 30)):
        raise ValueError("unexpected Matsuura first-page triangle shape")
    if len(second_page_rows) != len(station_order) - 30 or any(len(row) != 30 for row in second_page_rows):
        raise ValueError("unexpected Matsuura second-page front-block shape")
    if [len(row) for row in third_page_rows] != list(range(1, len(station_order) - 30)):
        raise ValueError("unexpected Matsuura third-page rear triangle shape")

    fare_rows: list[tuple[str, list[int]]] = []
    for row_index, fares in enumerate(first_page_rows, start=1):
        fare_rows.append((station_order[row_index], fares))
    for offset, front_fares in enumerate(second_page_rows):
        row_index = 30 + offset
        rear_fares = third_page_rows[offset - 1] if offset else []
        fares = [*front_fares, *rear_fares]
        if len(fares) != row_index:
            raise ValueError(f"Matsuura {station_order[row_index]} fare row has {len(fares)} fares, expected {row_index}")
        fare_rows.append((station_order[row_index], fares))

    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Matsuura Railway pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_single_pdf_triangle_pairs(
    raw_text: str,
    station_order: list[str],
    *,
    source_name: str,
) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    for line in raw_text.splitlines():
        line = line.split("令和", 1)[0]
        values = [
            int(value.replace(",", ""))
            for value in re.findall(r"\d[\d,]*", line)
        ]
        if not values:
            continue
        row_index = len(values)
        if row_index >= len(station_order):
            raise ValueError(f"{source_name} fare row is too long: {line}")
        fare_rows.append((station_order[row_index], values))
    if len(fare_rows) != len(station_order) - 1:
        raise ValueError(f"{source_name} has {len(fare_rows)} fare rows, expected {len(station_order) - 1}")
    for expected_index, (station_name, fares) in enumerate(fare_rows, start=1):
        if len(fares) != expected_index:
            raise ValueError(f"{source_name} {station_name} fare row has {len(fares)} fares, expected {expected_index}")
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"{source_name} pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_echizen_katsuyama_pairs(raw_text: str, station_order: list[str]) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    lines = raw_text.splitlines()
    for station_index, station_name in enumerate(station_order[1:], start=1):
        row_number = station_index + 2
        normalized_station = re.sub(r"\s+", "", station_name)
        matches: list[list[int]] = []
        for line in lines:
            for match in re.finditer(rf"(?<!\d){row_number}(?!\d)", line):
                if match.start() < 120:
                    continue
                tail = line[match.end():]
                if normalized_station not in re.sub(r"\s+", "", tail):
                    continue
                values = [
                    int(value.replace(",", ""))
                    for value in re.findall(r"\d[\d,]*", tail)
                ]
                if len(values) == station_index:
                    matches.append(values)
        if len(matches) != 1:
            raise ValueError(f"Echizen Katsuyama row {row_number} {station_name} matched {len(matches)} rows")
        fare_rows.append((station_name, list(reversed(matches[0]))))
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Echizen Katsuyama pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_prefix_triangle_pdf_pairs(
    raw_text: str,
    station_order: list[str],
    *,
    source_name: str,
) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    expected_count = 1
    for line in raw_text.splitlines():
        values = [
            int(value.replace(",", ""))
            for value in re.findall(r"\d[\d,]*", line)
        ]
        if len(values) < expected_count:
            continue
        fare_rows.append((station_order[expected_count], values[:expected_count]))
        expected_count += 1
        if expected_count == len(station_order):
            break
    if len(fare_rows) != len(station_order) - 1:
        raise ValueError(f"{source_name} has {len(fare_rows)} fare rows, expected {len(station_order) - 1}")
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"{source_name} pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_ichibata_pairs(
    elements: list[dict[str, Any]],
    station_order: list[str],
    sample_pairs: dict[str, int],
) -> dict[str, dict[str, Any]]:
    numeric_rows: dict[int, list[tuple[int, list[int]]]] = {}
    for element in elements:
        top = int(element["top"])
        if top < 160 or top > 760:
            continue
        text = element["text"].translate(str.maketrans("０１２３４５６７８９，", "0123456789,"))
        if not re.fullmatch(r"[0-9, ]+", text):
            continue
        values = [int(value.replace(",", "")) for value in re.findall(r"\d[\d,]*", text)]
        if values:
            numeric_rows.setdefault(top, []).append((int(element["left"]), values))

    row_tops = sorted(numeric_rows)[:len(station_order) - 1]
    if len(row_tops) != len(station_order) - 1:
        raise ValueError(f"Ichibata fare PDF has {len(row_tops)} fare rows, expected {len(station_order) - 1}")

    fare_rows: list[tuple[str, list[int]]] = []
    for row_index, top in enumerate(row_tops):
        expected = len(station_order) - row_index - 1
        chunks = sorted(numeric_rows[top])
        suffix_values: list[int] = []
        for _left, values in reversed(chunks):
            suffix_values = [*values, *suffix_values]
            if len(suffix_values) >= expected:
                break
        if len(suffix_values) != expected:
            raise ValueError(
                f"Ichibata row {row_index} {station_order[row_index]} has "
                f"{len(suffix_values)} adult fares, expected {expected}"
            )
        if any(value < 190 for value in suffix_values):
            raise ValueError(f"Ichibata row {row_index} adult suffix includes child fare values: {suffix_values}")
        fare_rows.append((station_order[row_index], suffix_values))

    pairs = manual_station_pairs(station_pair_upper_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Ichibata pair count {len(pairs)} != {expected_pair_count}")
    for pair_key, expected_yen in sample_pairs.items():
        actual_yen = pairs.get(pair_key, {}).get("yen")
        if actual_yen != expected_yen:
            raise ValueError(f"Ichibata sample {pair_key} is {actual_yen}, expected {expected_yen}")
    return pairs


def parse_keihan_otsu_station_pdf_pairs(
    origin_name: str,
    lines: list[str],
    station_names: set[str],
) -> dict[str, dict[str, Any]]:
    pairs: dict[str, dict[str, Any]] = {}
    in_otsu_section = False
    for line in lines:
        if line == "大津線":
            in_otsu_section = True
            continue
        if in_otsu_section and line.startswith("京都市営地下鉄"):
            break
        if not in_otsu_section:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        destination_name = parts[0]
        if destination_name not in station_names or destination_name == origin_name:
            continue
        try:
            float(parts[1])
        except ValueError:
            continue
        yen = parse_first_money(parts[2])
        add_station_pair(pairs, origin_name, destination_name, yen)
    return pairs


def parse_nagano_dentetsu_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    fare_rows: list[tuple[str, list[int]]] = []
    for station_index, station_name in enumerate(station_order[1:], start=1):
        if station_name == "附属中学前":
            row_line = next((line for line in lines if "附属中" in line and len(re.findall(r"\d{3,4}", line)) >= station_index), None)
        else:
            row_line = next((line for line in lines if station_name in line and len(re.findall(r"\d{3,4}", line)) >= station_index), None)
        if row_line is None:
            raise ValueError(f"missing Nagano Dentetsu fare row for {station_name}")
        fares = [int(value) for value in re.findall(r"\d{3,4}", row_line)[:station_index]]
        if len(fares) != station_index:
            raise ValueError(f"Nagano Dentetsu {station_name} fare row has {len(fares)} fares, expected {station_index}")
        fare_rows.append((station_name, fares))
    pairs = manual_station_pairs(station_pair_triangle_rows(station_order, fare_rows))
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pairs) != expected_pair_count:
        raise ValueError(f"Nagano Dentetsu pair count {len(pairs)} != {expected_pair_count}")
    return pairs


def parse_kantetsu_pairs(lines: list[str], station_order: list[str]) -> dict[str, dict[str, Any]]:
    station_names = set(station_order)
    stations_by_length = sorted(station_order, key=len, reverse=True)
    pairs: dict[str, dict[str, Any]] = {}
    current_origin: str | None = None
    for line in lines:
        normalized = re.sub(r"\s+", "", line)
        header_match = re.search(r"(?:常総線|竜ヶ崎線)(.+?)駅", normalized)
        if header_match and header_match.group(1) in station_names:
            current_origin = header_match.group(1)
            continue
        if current_origin is None or "当駅" in normalized:
            continue
        dest_name = next((station for station in stations_by_length if normalized.startswith(station)), None)
        if not dest_name or dest_name == current_origin:
            continue
        values = re.findall(r"\d+\.\d+|\d[\d,]*", line)
        if len(values) < 3:
            continue
        add_station_pair(pairs, current_origin, dest_name, parse_first_money(values[1]))
    return pairs


def parse_compact_forward_triangle_pairs(
    lines: list[str],
    station_order: list[str],
    *,
    source_name: str,
    row_labels: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    pairs: list[tuple[str, str, int]] = []
    for station_index, station_name in enumerate(station_order[:-1]):
        expected_count = len(station_order) - station_index - 1
        row_label = (row_labels or {}).get(station_name, station_name)
        row_fares = None
        for line in lines:
            normalized = re.sub(r"\s+", "", line)
            position = normalized.find(row_label)
            if position < 0:
                continue
            match = re.match(r"(?:\d{3})+", normalized[position + len(row_label):])
            if not match:
                continue
            chunks = [int(match.group(0)[offset:offset + 3]) for offset in range(0, len(match.group(0)), 3)]
            if len(chunks) >= expected_count:
                row_fares = chunks[:expected_count]
                break
        if row_fares is None:
            raise ValueError(f"missing {source_name} fare row for {station_name}")
        for target_name, yen in zip(station_order[station_index + 1:], row_fares, strict=True):
            pairs.append((station_name, target_name, yen))
    pair_table = manual_station_pairs(pairs)
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pair_table) != expected_pair_count:
        raise ValueError(f"{source_name} pair count {len(pair_table)} != {expected_pair_count}")
    return pair_table


def parse_spaced_forward_triangle_pairs(
    lines: list[str],
    station_order: list[str],
    *,
    source_name: str,
    row_labels: dict[str, str] | None = None,
    max_fare_yen: int = 5000,
) -> dict[str, dict[str, Any]]:
    pairs: list[tuple[str, str, int]] = []
    for station_index, station_name in enumerate(station_order[:-1]):
        expected_count = len(station_order) - station_index - 1
        row_label = (row_labels or {}).get(station_name, station_name)
        row_fares = None
        for line in lines:
            position = line.rfind(row_label)
            if position < 0:
                continue
            values = [parse_first_money(value) for value in re.findall(r"\d[\d,]*", line[position + len(row_label):])]
            if len(values) >= expected_count and all(100 <= value <= max_fare_yen for value in values[:expected_count]):
                row_fares = values[:expected_count]
                break
        if row_fares is None:
            raise ValueError(f"missing {source_name} fare row for {station_name}")
        for target_name, yen in zip(station_order[station_index + 1:], row_fares, strict=True):
            pairs.append((station_name, target_name, yen))
    pair_table = manual_station_pairs(pairs)
    expected_pair_count = len(station_order) * (len(station_order) - 1) // 2
    if len(pair_table) != expected_pair_count:
        raise ValueError(f"{source_name} pair count {len(pair_table)} != {expected_pair_count}")
    return pair_table


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

    yoro = YORO_RAILWAY_STATION_PAIR_SOURCE
    yoro_cache_path, yoro_lines = fetch_pdf_text(yoro["url"], cache_dir)
    yoro_pairs = parse_yoro_railway_pairs(yoro_lines, yoro["stationOrder"])
    sources.append({
        "key": yoro["key"],
        "url": yoro["url"],
        "cachePath": yoro_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": yoro["operatorIds"],
        "operatorName": yoro["operatorName"],
        "extraction": "parsed_adult_rows_from_official_pdf",
        "pairCount": len(yoro_pairs),
    })
    station_pair_tables[yoro["key"]] = {
        "operatorIds": yoro["operatorIds"],
        "routeIds": yoro["routeIds"],
        "sourceKey": yoro["key"],
        "operatorName": yoro["operatorName"],
        "notes": yoro["notes"],
        "pairs": yoro_pairs,
    }

    matsuura = MATSUURA_RAILWAY_STATION_PAIR_SOURCE
    matsuura_cache_path, matsuura_raw_text = fetch_pdf_raw_text(matsuura["url"], cache_dir)
    matsuura_pairs = parse_matsuura_railway_pairs(
        matsuura_raw_text,
        matsuura["stationOrder"],
    )
    sources.append({
        "key": matsuura["key"],
        "url": matsuura["url"],
        "cachePath": matsuura_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": matsuura["operatorIds"],
        "operatorName": matsuura["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_pdf",
        "pairCount": len(matsuura_pairs),
    })
    station_pair_tables[matsuura["key"]] = {
        "operatorIds": matsuura["operatorIds"],
        "routeIds": matsuura["routeIds"],
        "sourceKey": matsuura["key"],
        "operatorName": matsuura["operatorName"],
        "notes": matsuura["notes"],
        "pairs": matsuura_pairs,
    }

    nagaragawa = NAGARAGAWA_RAILWAY_STATION_PAIR_SOURCE
    nagaragawa_cache_path, nagaragawa_raw_text = fetch_pdf_raw_text(nagaragawa["url"], cache_dir)
    nagaragawa_pairs = parse_single_pdf_triangle_pairs(
        nagaragawa_raw_text,
        nagaragawa["stationOrder"],
        source_name="Nagaragawa Railway",
    )
    sources.append({
        "key": nagaragawa["key"],
        "url": nagaragawa["url"],
        "cachePath": nagaragawa_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": nagaragawa["operatorIds"],
        "operatorName": nagaragawa["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_pdf",
        "pairCount": len(nagaragawa_pairs),
    })
    station_pair_tables[nagaragawa["key"]] = {
        "operatorIds": nagaragawa["operatorIds"],
        "routeIds": nagaragawa["routeIds"],
        "sourceKey": nagaragawa["key"],
        "operatorName": nagaragawa["operatorName"],
        "notes": nagaragawa["notes"],
        "pairs": nagaragawa_pairs,
    }

    echizen_katsuyama = ECHIZEN_KATSUYAMA_STATION_PAIR_SOURCE
    echizen_cache_path, echizen_raw_text = fetch_pdf_raw_text(echizen_katsuyama["url"], cache_dir)
    echizen_pairs = parse_echizen_katsuyama_pairs(
        echizen_raw_text,
        echizen_katsuyama["stationOrder"],
    )
    sources.append({
        "key": echizen_katsuyama["key"],
        "url": echizen_katsuyama["url"],
        "cachePath": echizen_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": echizen_katsuyama["operatorIds"],
        "operatorName": echizen_katsuyama["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_pdf",
        "pairCount": len(echizen_pairs),
    })
    station_pair_tables[echizen_katsuyama["key"]] = {
        "operatorIds": echizen_katsuyama["operatorIds"],
        "routeIds": echizen_katsuyama["routeIds"],
        "sourceKey": echizen_katsuyama["key"],
        "operatorName": echizen_katsuyama["operatorName"],
        "notes": echizen_katsuyama["notes"],
        "pairs": echizen_pairs,
    }

    tosakuro_nakamura_sukumo = TOSAKURO_NAKAMURA_SUKUMO_STATION_PAIR_SOURCE
    tosakuro_cache_path, tosakuro_raw_text = fetch_pdf_raw_text(tosakuro_nakamura_sukumo["url"], cache_dir)
    tosakuro_pairs = parse_prefix_triangle_pdf_pairs(
        tosakuro_raw_text,
        tosakuro_nakamura_sukumo["stationOrder"],
        source_name="Tosa Kuroshio Nakamura-Sukumo Line",
    )
    sources.append({
        "key": tosakuro_nakamura_sukumo["key"],
        "url": tosakuro_nakamura_sukumo["url"],
        "cachePath": tosakuro_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": tosakuro_nakamura_sukumo["operatorIds"],
        "operatorName": tosakuro_nakamura_sukumo["operatorName"],
        "extraction": "parsed_station_pair_matrix_from_official_pdf",
        "pairCount": len(tosakuro_pairs),
    })
    station_pair_tables[tosakuro_nakamura_sukumo["key"]] = {
        "operatorIds": tosakuro_nakamura_sukumo["operatorIds"],
        "routeIds": tosakuro_nakamura_sukumo["routeIds"],
        "sourceKey": tosakuro_nakamura_sukumo["key"],
        "operatorName": tosakuro_nakamura_sukumo["operatorName"],
        "notes": tosakuro_nakamura_sukumo["notes"],
        "pairs": tosakuro_pairs,
    }

    ichibata = ICHIBATA_STATION_PAIR_SOURCE
    ichibata_cache_path, ichibata_elements = fetch_pdf_xml_text_elements(ichibata["url"], cache_dir)
    ichibata_pairs = parse_ichibata_pairs(
        ichibata_elements,
        ichibata["stationOrder"],
        ichibata["samplePairs"],
    )
    sources.append({
        "key": ichibata["key"],
        "url": ichibata["url"],
        "cachePath": ichibata_cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": ichibata["operatorIds"],
        "operatorName": ichibata["operatorName"],
        "extraction": "parsed_adult_station_pair_matrix_from_official_pdf_xml",
        "pairCount": len(ichibata_pairs),
    })
    station_pair_tables[ichibata["key"]] = {
        "operatorIds": ichibata["operatorIds"],
        "routeIds": ichibata["routeIds"],
        "sourceKey": ichibata["key"],
        "operatorName": ichibata["operatorName"],
        "notes": ichibata["notes"],
        "pairs": ichibata_pairs,
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

    keihan_ishiyama_sakamoto = KEIHAN_ISHIYAMA_SAKAMOTO_STATION_PAIR_SOURCE
    keihan_ishiyama_sakamoto_pairs: dict[str, dict[str, Any]] = {}
    keihan_ishiyama_sakamoto_cache_paths: list[str] = []
    keihan_ishiyama_sakamoto_stations = set(keihan_ishiyama_sakamoto["stationOrder"])
    for origin_name, url in keihan_ishiyama_sakamoto["pages"]:
        cache_path, lines = fetch_pdf_text(url, cache_dir)
        keihan_ishiyama_sakamoto_cache_paths.append(cache_path)
        for pair in parse_keihan_otsu_station_pdf_pairs(
            origin_name,
            lines,
            keihan_ishiyama_sakamoto_stations,
        ).values():
            add_station_pair(
                keihan_ishiyama_sakamoto_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    expected_keihan_ishiyama_sakamoto_pairs = (
        len(keihan_ishiyama_sakamoto["stationOrder"]) * (len(keihan_ishiyama_sakamoto["stationOrder"]) - 1) // 2
    )
    if len(keihan_ishiyama_sakamoto_pairs) != expected_keihan_ishiyama_sakamoto_pairs:
        raise ValueError(
            f"Keihan Ishiyama-Sakamoto pair count {len(keihan_ishiyama_sakamoto_pairs)} "
            f"!= {expected_keihan_ishiyama_sakamoto_pairs}"
        )
    sources.append({
        "key": keihan_ishiyama_sakamoto["key"],
        "urls": [url for _origin_name, url in keihan_ishiyama_sakamoto["pages"]],
        "cachePaths": keihan_ishiyama_sakamoto_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": keihan_ishiyama_sakamoto["operatorIds"],
        "operatorName": keihan_ishiyama_sakamoto["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pdf_pages",
        "pairCount": len(keihan_ishiyama_sakamoto_pairs),
    })
    station_pair_tables[keihan_ishiyama_sakamoto["key"]] = {
        "operatorIds": keihan_ishiyama_sakamoto["operatorIds"],
        "routeIds": keihan_ishiyama_sakamoto["routeIds"],
        "sourceKey": keihan_ishiyama_sakamoto["key"],
        "operatorName": keihan_ishiyama_sakamoto["operatorName"],
        "notes": keihan_ishiyama_sakamoto["notes"],
        "pairs": keihan_ishiyama_sakamoto_pairs,
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

    joshin = JOSHIN_DENTETSU_STATION_PAIR_SOURCE
    joshin_pairs: dict[str, dict[str, Any]] = {}
    joshin_cache_paths: list[str] = []
    for origin_name, url in joshin["pages"]:
        cache_path, lines = fetch_text(url, cache_dir)
        joshin_cache_paths.append(cache_path)
        for pair in parse_joshin_dentetsu_page(origin_name, lines, joshin["stationOrder"]).values():
            add_station_pair(
                joshin_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    expected_joshin_pairs = len(joshin["stationOrder"]) * (len(joshin["stationOrder"]) - 1) // 2
    if len(joshin_pairs) != expected_joshin_pairs:
        raise ValueError(f"Joshin Dentetsu pair count {len(joshin_pairs)} != {expected_joshin_pairs}")
    sources.append({
        "key": joshin["key"],
        "urls": [url for _origin_name, url in joshin["pages"]],
        "cachePaths": joshin_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": joshin["operatorIds"],
        "operatorName": joshin["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pages",
        "pairCount": len(joshin_pairs),
    })
    station_pair_tables[joshin["key"]] = {
        "operatorIds": joshin["operatorIds"],
        "routeIds": joshin["routeIds"],
        "sourceKey": joshin["key"],
        "operatorName": joshin["operatorName"],
        "notes": joshin["notes"],
        "pairs": joshin_pairs,
    }

    jomo = JOMO_RAILWAY_STATION_PAIR_SOURCE
    cache_path, html = fetch_raw(jomo["url"], cache_dir)
    jomo_pairs = parse_jomo_railway_pairs(html, jomo["stationOrder"])
    sources.append({
        "key": jomo["key"],
        "url": jomo["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": jomo["operatorIds"],
        "operatorName": jomo["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_html",
        "pairCount": len(jomo_pairs),
    })
    station_pair_tables[jomo["key"]] = {
        "operatorIds": jomo["operatorIds"],
        "routeIds": jomo["routeIds"],
        "sourceKey": jomo["key"],
        "operatorName": jomo["operatorName"],
        "notes": jomo["notes"],
        "pairs": jomo_pairs,
    }

    chichibu = CHICHIBU_RAILWAY_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(chichibu["url"], cache_dir)
    chichibu_pairs = parse_chichibu_railway_pairs(lines, chichibu["stationOrder"])
    sources.append({
        "key": chichibu["key"],
        "url": chichibu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": chichibu["operatorIds"],
        "operatorName": chichibu["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_pdf",
        "pairCount": len(chichibu_pairs),
    })
    station_pair_tables[chichibu["key"]] = {
        "operatorIds": chichibu["operatorIds"],
        "routeIds": chichibu["routeIds"],
        "sourceKey": chichibu["key"],
        "operatorName": chichibu["operatorName"],
        "notes": chichibu["notes"],
        "pairs": chichibu_pairs,
    }

    tenhama = TENHAMA_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(tenhama["url"], cache_dir)
    tenhama_pairs = parse_numbered_pdf_triangle_pairs(
        lines,
        tenhama["stationOrder"],
        source_name="Tenhama",
    )
    sources.append({
        "key": tenhama["key"],
        "url": tenhama["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": tenhama["operatorIds"],
        "operatorName": tenhama["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(tenhama_pairs),
    })
    station_pair_tables[tenhama["key"]] = {
        "operatorIds": tenhama["operatorIds"],
        "routeIds": tenhama["routeIds"],
        "sourceKey": tenhama["key"],
        "operatorName": tenhama["operatorName"],
        "notes": tenhama["notes"],
        "pairs": tenhama_pairs,
    }

    nagano_dentetsu = NAGANO_DENTETSU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(nagano_dentetsu["url"], cache_dir)
    nagano_dentetsu_pairs = parse_nagano_dentetsu_pairs(lines, nagano_dentetsu["stationOrder"])
    sources.append({
        "key": nagano_dentetsu["key"],
        "url": nagano_dentetsu["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": nagano_dentetsu["operatorIds"],
        "operatorName": nagano_dentetsu["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(nagano_dentetsu_pairs),
    })
    station_pair_tables[nagano_dentetsu["key"]] = {
        "operatorIds": nagano_dentetsu["operatorIds"],
        "routeIds": nagano_dentetsu["routeIds"],
        "sourceKey": nagano_dentetsu["key"],
        "operatorName": nagano_dentetsu["operatorName"],
        "notes": nagano_dentetsu["notes"],
        "pairs": nagano_dentetsu_pairs,
    }

    kantetsu = KANTETSU_STATION_PAIR_SOURCE
    kantetsu_pairs: dict[str, dict[str, Any]] = {}
    kantetsu_cache_paths: list[str] = []
    for page in kantetsu["pages"]:
        url = kantetsu["baseUrl"] + page
        cache_path, lines = fetch_pdf_text(url, cache_dir)
        kantetsu_cache_paths.append(cache_path)
        for pair in parse_kantetsu_pairs(lines, kantetsu["stationOrder"]).values():
            add_station_pair(
                kantetsu_pairs,
                pair["fromStationName"],
                pair["toStationName"],
                pair["yen"],
            )
    expected_kantetsu_pairs = (
        25 * 24 // 2
        + 3 * 2 // 2
    )
    if len(kantetsu_pairs) != expected_kantetsu_pairs:
        raise ValueError(f"Kantetsu pair count {len(kantetsu_pairs)} != {expected_kantetsu_pairs}")
    sources.append({
        "key": kantetsu["key"],
        "urls": [kantetsu["baseUrl"] + page for page in kantetsu["pages"]],
        "cachePaths": kantetsu_cache_paths,
        "kind": "station_pair_fare_table",
        "operatorIds": kantetsu["operatorIds"],
        "operatorName": kantetsu["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_station_pdfs",
        "pairCount": len(kantetsu_pairs),
    })
    station_pair_tables[kantetsu["key"]] = {
        "operatorIds": kantetsu["operatorIds"],
        "routeIds": kantetsu["routeIds"],
        "sourceKey": kantetsu["key"],
        "operatorName": kantetsu["operatorName"],
        "notes": kantetsu["notes"],
        "pairs": kantetsu_pairs,
    }

    for sangi in SANGI_RAILWAY_STATION_PAIR_SOURCES:
        cache_path, lines = fetch_pdf_text(sangi["url"], cache_dir)
        sangi_pairs = parse_compact_forward_triangle_pairs(
            lines,
            sangi["stationOrder"],
            source_name=sangi["key"],
            row_labels=sangi.get("rowLabels"),
        )
        sources.append({
            "key": sangi["key"],
            "url": sangi["url"],
            "cachePath": cache_path,
            "kind": "station_pair_fare_table",
            "operatorIds": sangi["operatorIds"],
            "operatorName": sangi["operatorName"],
            "extraction": "parsed_compact_station_pair_triangle_from_official_pdf",
            "pairCount": len(sangi_pairs),
        })
        station_pair_tables[sangi["key"]] = {
            "operatorIds": sangi["operatorIds"],
            "routeIds": sangi["routeIds"],
            "sourceKey": sangi["key"],
            "operatorName": sangi["operatorName"],
            "notes": sangi["notes"],
            "pairs": sangi_pairs,
        }

    akita_nairiku = AKITA_NAIRIKU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_pdf_text(akita_nairiku["url"], cache_dir)
    akita_nairiku_pairs = parse_spaced_forward_triangle_pairs(
        lines,
        akita_nairiku["stationOrder"],
        source_name=akita_nairiku["key"],
        row_labels=akita_nairiku["rowLabels"],
    )
    sources.append({
        "key": akita_nairiku["key"],
        "url": akita_nairiku["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": akita_nairiku["operatorIds"],
        "operatorName": akita_nairiku["operatorName"],
        "extraction": "parsed_station_pair_triangle_from_official_pdf",
        "pairCount": len(akita_nairiku_pairs),
    })
    station_pair_tables[akita_nairiku["key"]] = {
        "operatorIds": akita_nairiku["operatorIds"],
        "routeIds": akita_nairiku["routeIds"],
        "sourceKey": akita_nairiku["key"],
        "operatorName": akita_nairiku["operatorName"],
        "notes": akita_nairiku["notes"],
        "pairs": akita_nairiku_pairs,
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

    nishikigawa_railway = NISHIKIGAWA_RAILWAY_STATION_PAIR_SOURCE
    cache_path, lines = fetch_text(nishikigawa_railway["url"], cache_dir)
    nishikigawa_railway_pairs = parse_nishikigawa_railway_pairs(
        lines,
        nishikigawa_railway["stationOrder"],
    )
    sources.append({
        "key": nishikigawa_railway["key"],
        "url": nishikigawa_railway["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": nishikigawa_railway["operatorIds"],
        "operatorName": nishikigawa_railway["operatorName"],
        "extraction": "parsed_station_pair_table_from_official_html",
        "pairCount": len(nishikigawa_railway_pairs),
    })
    station_pair_tables[nishikigawa_railway["key"]] = {
        "operatorIds": nishikigawa_railway["operatorIds"],
        "routeIds": nishikigawa_railway["routeIds"],
        "sourceKey": nishikigawa_railway["key"],
        "operatorName": nishikigawa_railway["operatorName"],
        "notes": nishikigawa_railway["notes"],
        "pairs": nishikigawa_railway_pairs,
    }

    watarase_keikoku = WATARASE_KEIKOKU_STATION_PAIR_SOURCE
    cache_path, lines = fetch_text(watarase_keikoku["url"], cache_dir)
    watarase_keikoku_pairs = parse_watarase_keikoku_pairs(
        lines,
        watarase_keikoku["stationOrder"],
    )
    sources.append({
        "key": watarase_keikoku["key"],
        "url": watarase_keikoku["url"],
        "cachePath": cache_path,
        "kind": "station_pair_fare_table",
        "operatorIds": watarase_keikoku["operatorIds"],
        "operatorName": watarase_keikoku["operatorName"],
        "extraction": "parsed_station_pair_tables_from_official_html",
        "pairCount": len(watarase_keikoku_pairs),
    })
    station_pair_tables[watarase_keikoku["key"]] = {
        "operatorIds": watarase_keikoku["operatorIds"],
        "routeIds": watarase_keikoku["routeIds"],
        "sourceKey": watarase_keikoku["key"],
        "operatorName": watarase_keikoku["operatorName"],
        "notes": watarase_keikoku["notes"],
        "pairs": watarase_keikoku_pairs,
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
