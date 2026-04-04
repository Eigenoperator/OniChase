#!/usr/bin/env python3

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
VISUALS_DIR = ROOT / "visuals"
STATIONS_PATH = DATA_DIR / "shinkansen_v2_stations.json"
ROUTES_PATH = DATA_DIR / "shinkansen_v2_routes.json"


STATIONS = [
    {"id": "TOKYO", "name": "Tokyo", "category": "hub", "x": 1310, "y": 1790, "lat": None, "lon": None},
    {"id": "UENO", "name": "Ueno", "category": "hub", "x": 1320, "y": 1718, "lat": None, "lon": None},
    {"id": "OMIYA", "name": "Omiya", "category": "hub", "x": 1332, "y": 1646, "lat": None, "lon": None},
    {"id": "KUMAGAYA", "name": "Kumagaya", "category": "normal", "x": 1352, "y": 1560, "lat": None, "lon": None},
    {"id": "HONJO_WASEDA", "name": "Honjo-Waseda", "category": "normal", "x": 1372, "y": 1480, "lat": None, "lon": None},
    {"id": "TAKASAKI", "name": "Takasaki", "category": "hub", "x": 1394, "y": 1400, "lat": None, "lon": None},
    {"id": "OYAMA", "name": "Oyama", "category": "normal", "x": 1384, "y": 1538, "lat": None, "lon": None},
    {"id": "UTSUNOMIYA", "name": "Utsunomiya", "category": "normal", "x": 1420, "y": 1456, "lat": None, "lon": None},
    {"id": "NASUSHIOBARA", "name": "Nasushiobara", "category": "normal", "x": 1456, "y": 1368, "lat": None, "lon": None},
    {"id": "SHIN_SHIRAKAWA", "name": "Shin-Shirakawa", "category": "normal", "x": 1492, "y": 1282, "lat": None, "lon": None},
    {"id": "KORIYAMA", "name": "Koriyama", "category": "normal", "x": 1528, "y": 1196, "lat": None, "lon": None},
    {"id": "FUKUSHIMA", "name": "Fukushima", "category": "hub", "x": 1564, "y": 1108, "lat": None, "lon": None},
    {"id": "SHIROISHI_ZAO", "name": "Shiroishi-Zao", "category": "normal", "x": 1600, "y": 1022, "lat": None, "lon": None},
    {"id": "SENDAI_TOHOKU", "name": "Sendai", "category": "hub", "x": 1636, "y": 936, "lat": None, "lon": None},
    {"id": "FURUKAWA", "name": "Furukawa", "category": "normal", "x": 1668, "y": 852, "lat": None, "lon": None},
    {"id": "KURIKOMA_KOGEN", "name": "Kurikoma-Kogen", "category": "normal", "x": 1700, "y": 770, "lat": None, "lon": None},
    {"id": "ICHINOSEKI", "name": "Ichinoseki", "category": "normal", "x": 1734, "y": 688, "lat": None, "lon": None},
    {"id": "MIZUSAWA_ESASHI", "name": "Mizusawa-Esashi", "category": "normal", "x": 1766, "y": 616, "lat": None, "lon": None},
    {"id": "KITAKAMI", "name": "Kitakami", "category": "normal", "x": 1796, "y": 546, "lat": None, "lon": None},
    {"id": "SHIN_HANAMAKI", "name": "Shin-Hanamaki", "category": "normal", "x": 1826, "y": 478, "lat": None, "lon": None},
    {"id": "MORIOKA", "name": "Morioka", "category": "hub", "x": 1858, "y": 410, "lat": None, "lon": None},
    {"id": "IWATE_NUMAKUNAI", "name": "Iwate-Numakunai", "category": "normal", "x": 1890, "y": 340, "lat": None, "lon": None},
    {"id": "NINOHE", "name": "Ninohe", "category": "normal", "x": 1922, "y": 272, "lat": None, "lon": None},
    {"id": "HACHINOHE", "name": "Hachinohe", "category": "normal", "x": 1954, "y": 204, "lat": None, "lon": None},
    {"id": "SHICHINOHE_TOWADA", "name": "Shichinohe-Towada", "category": "normal", "x": 1986, "y": 136, "lat": None, "lon": None},
    {"id": "SHIN_AOMORI", "name": "Shin-Aomori", "category": "hub", "x": 2018, "y": 72, "lat": None, "lon": None},
    {"id": "OKU_TSUGARU_IMABETSU", "name": "Oku-Tsugaru-Imabetsu", "category": "normal", "x": 2062, "y": 24, "lat": None, "lon": None},
    {"id": "KIKONAI", "name": "Kikonai", "category": "normal", "x": 2108, "y": -20, "lat": None, "lon": None},
    {"id": "SHIN_HAKODATE_HOKUTO", "name": "Shin-Hakodate-Hokuto", "category": "hub", "x": 2154, "y": -64, "lat": None, "lon": None},
    {"id": "YONEZAWA", "name": "Yonezawa", "category": "normal", "x": 1478, "y": 1138, "lat": None, "lon": None},
    {"id": "TAKAHATA", "name": "Takahata", "category": "normal", "x": 1418, "y": 1168},
    {"id": "AKAYU", "name": "Akayu", "category": "normal", "x": 1358, "y": 1202},
    {"id": "KAMINOYAMA_ONSEN", "name": "Kaminoyama-Onsen", "category": "normal", "x": 1298, "y": 1238},
    {"id": "YAMAGATA", "name": "Yamagata", "category": "hub", "x": 1238, "y": 1274},
    {"id": "TENDO", "name": "Tendo", "category": "normal", "x": 1178, "y": 1310},
    {"id": "SAKURANBO_HIGASHINE", "name": "Sakuranbo-Higashine", "category": "normal", "x": 1118, "y": 1348},
    {"id": "MURAYAMA", "name": "Murayama", "category": "normal", "x": 1058, "y": 1388},
    {"id": "OISHIDA", "name": "Oishida", "category": "normal", "x": 998, "y": 1428},
    {"id": "SHINJO", "name": "Shinjo", "category": "hub", "x": 938, "y": 1468},
    {"id": "SHIZUKUISHI", "name": "Shizukuishi", "category": "normal", "x": 1788, "y": 458},
    {"id": "TAZAWAKO", "name": "Tazawako", "category": "normal", "x": 1718, "y": 508},
    {"id": "KAKUNODATE", "name": "Kakunodate", "category": "normal", "x": 1650, "y": 560},
    {"id": "OMAGARI", "name": "Omagari", "category": "hub", "x": 1582, "y": 614},
    {"id": "AKITA", "name": "Akita", "category": "hub", "x": 1514, "y": 668},
    {"id": "JOMO_KOGEN", "name": "Jomo-Kogen", "category": "normal", "x": 1354, "y": 1340},
    {"id": "ECHIGO_YUZAWA", "name": "Echigo-Yuzawa", "category": "hub", "x": 1300, "y": 1286},
    {"id": "GALA_YUZAWA", "name": "Gala Yuzawa", "category": "normal", "x": 1266, "y": 1240},
    {"id": "URASA", "name": "Urasa", "category": "normal", "x": 1246, "y": 1220},
    {"id": "NAGAOKA", "name": "Nagaoka", "category": "hub", "x": 1192, "y": 1148},
    {"id": "TSUBAME_SANJO", "name": "Tsubame-Sanjo", "category": "normal", "x": 1136, "y": 1076},
    {"id": "NIIGATA", "name": "Niigata", "category": "hub", "x": 1080, "y": 1004},
    {"id": "ANNAKA_HARUNA", "name": "Annaka-Haruna", "category": "normal", "x": 1358, "y": 1450},
    {"id": "KARUIZAWA", "name": "Karuizawa", "category": "normal", "x": 1292, "y": 1478},
    {"id": "SAKUDAIRA", "name": "Sakudaira", "category": "normal", "x": 1228, "y": 1508},
    {"id": "UEDA", "name": "Ueda", "category": "normal", "x": 1164, "y": 1538},
    {"id": "NAGANO", "name": "Nagano", "category": "hub", "x": 1100, "y": 1568},
    {"id": "IIYAMA", "name": "Iiyama", "category": "normal", "x": 1034, "y": 1598},
    {"id": "JOETSUMYOKO", "name": "Joetsumyoko", "category": "hub", "x": 968, "y": 1628},
    {"id": "ITOIGAWA", "name": "Itoigawa", "category": "normal", "x": 900, "y": 1658},
    {"id": "KUROBE_UNAZUKIONSEN", "name": "Kurobe-Unazukionsen", "category": "normal", "x": 832, "y": 1688},
    {"id": "TOYAMA", "name": "Toyama", "category": "hub", "x": 764, "y": 1718},
    {"id": "SHIN_TAKAOKA", "name": "Shin-Takaoka", "category": "normal", "x": 696, "y": 1748},
    {"id": "KANAZAWA", "name": "Kanazawa", "category": "hub", "x": 628, "y": 1778},
    {"id": "KOMATSU", "name": "Komatsu", "category": "normal", "x": 560, "y": 1808},
    {"id": "KAGAONSEN", "name": "Kagaonsen", "category": "normal", "x": 492, "y": 1838},
    {"id": "AWARAONSEN", "name": "Awaraonsen", "category": "normal", "x": 424, "y": 1868},
    {"id": "FUKUI", "name": "Fukui", "category": "hub", "x": 356, "y": 1898},
    {"id": "ECHIZEN_TAKEFU", "name": "Echizen-Takefu", "category": "normal", "x": 288, "y": 1928},
    {"id": "TSURUGA", "name": "Tsuruga", "category": "hub", "x": 220, "y": 1958},
    {"id": "SHINAGAWA", "name": "Shinagawa", "category": "hub", "x": 1220, "y": 1790},
    {"id": "SHIN_YOKOHAMA", "name": "Shin-Yokohama", "category": "hub", "x": 1120, "y": 1790},
    {"id": "ODAWARA", "name": "Odawara", "category": "normal", "x": 1030, "y": 1790},
    {"id": "ATAMI", "name": "Atami", "category": "normal", "x": 948, "y": 1790},
    {"id": "MISHIMA", "name": "Mishima", "category": "normal", "x": 866, "y": 1790},
    {"id": "SHIN_FUJI", "name": "Shin-Fuji", "category": "normal", "x": 784, "y": 1790},
    {"id": "SHIZUOKA", "name": "Shizuoka", "category": "hub", "x": 700, "y": 1790},
    {"id": "KAKEGAWA", "name": "Kakegawa", "category": "normal", "x": 620, "y": 1790},
    {"id": "HAMAMATSU", "name": "Hamamatsu", "category": "hub", "x": 544, "y": 1790},
    {"id": "TOYOHASHI", "name": "Toyohashi", "category": "normal", "x": 472, "y": 1790},
    {"id": "MIKAWA_ANJO", "name": "Mikawa-Anjo", "category": "normal", "x": 404, "y": 1790},
    {"id": "NAGOYA", "name": "Nagoya", "category": "hub", "x": 336, "y": 1790},
    {"id": "GIFU_HASHIMA", "name": "Gifu-Hashima", "category": "normal", "x": 268, "y": 1790},
    {"id": "MAIBARA", "name": "Maibara", "category": "hub", "x": 200, "y": 1790},
    {"id": "KYOTO", "name": "Kyoto", "category": "hub", "x": 130, "y": 1790},
    {"id": "SHIN_OSAKA", "name": "Shin-Osaka", "category": "hub", "x": 58, "y": 1790},
    {"id": "SHIN_KOBE", "name": "Shin-Kobe", "category": "hub", "x": -16, "y": 1790},
    {"id": "NISHI_AKASHI", "name": "Nishi-Akashi", "category": "normal", "x": -90, "y": 1790},
    {"id": "HIMEJI", "name": "Himeji", "category": "hub", "x": -164, "y": 1790},
    {"id": "AIOI", "name": "Aioi", "category": "normal", "x": -238, "y": 1790},
    {"id": "OKAYAMA", "name": "Okayama", "category": "hub", "x": -312, "y": 1790},
    {"id": "SHIN_KURASHIKI", "name": "Shin-Kurashiki", "category": "normal", "x": -386, "y": 1790},
    {"id": "FUKUYAMA", "name": "Fukuyama", "category": "hub", "x": -460, "y": 1790},
    {"id": "SHIN_ONOMICHI", "name": "Shin-Onomichi", "category": "normal", "x": -534, "y": 1790},
    {"id": "MIHARA", "name": "Mihara", "category": "normal", "x": -608, "y": 1790},
    {"id": "HIGASHI_HIROSHIMA", "name": "Higashi-Hiroshima", "category": "normal", "x": -682, "y": 1790},
    {"id": "HIROSHIMA", "name": "Hiroshima", "category": "hub", "x": -756, "y": 1790},
    {"id": "SHIN_IWAKUNI", "name": "Shin-Iwakuni", "category": "normal", "x": -830, "y": 1790},
    {"id": "TOKUYAMA", "name": "Tokuyama", "category": "hub", "x": -904, "y": 1790},
    {"id": "SHIN_YAMAGUCHI", "name": "Shin-Yamaguchi", "category": "hub", "x": -978, "y": 1790},
    {"id": "ASA", "name": "Asa", "category": "normal", "x": -1052, "y": 1790},
    {"id": "SHIN_SHIMONOSEKI", "name": "Shin-Shimonoseki", "category": "hub", "x": -1126, "y": 1790},
    {"id": "KOKURA", "name": "Kokura", "category": "hub", "x": -1200, "y": 1790},
    {"id": "HAKATA", "name": "Hakata", "category": "hub", "x": -1274, "y": 1790},
    {"id": "SHIN_TOSU", "name": "Shin-Tosu", "category": "hub", "x": -1262, "y": 1856},
    {"id": "KURUME", "name": "Kurume", "category": "hub", "x": -1252, "y": 1912},
    {"id": "CHIKUGO_FUNAGOYA", "name": "Chikugo-Funagoya", "category": "normal", "x": -1242, "y": 1968},
    {"id": "SHIN_OMUTA", "name": "Shin-Omuta", "category": "normal", "x": -1232, "y": 2024},
    {"id": "SHIN_TAMANA", "name": "Shin-Tamana", "category": "normal", "x": -1222, "y": 2080},
    {"id": "KUMAMOTO", "name": "Kumamoto", "category": "hub", "x": -1212, "y": 2136},
    {"id": "SHIN_YATSUSHIRO", "name": "Shin-Yatsushiro", "category": "hub", "x": -1202, "y": 2192},
    {"id": "SHIN_MINAMATA", "name": "Shin-Minamata", "category": "normal", "x": -1192, "y": 2248},
    {"id": "IZUMI", "name": "Izumi", "category": "normal", "x": -1182, "y": 2304},
    {"id": "SENDAI_KYUSHU", "name": "Sendai", "category": "hub", "x": -1172, "y": 2360},
    {"id": "KAGOSHIMA_CHUO", "name": "Kagoshima-Chuo", "category": "hub", "x": -1162, "y": 2416},
    {"id": "TAKEO_ONSEN", "name": "Takeo-Onsen", "category": "hub", "x": -1340, "y": 1832},
    {"id": "URESHINO_ONSEN", "name": "Ureshino-Onsen", "category": "normal", "x": -1420, "y": 1784},
    {"id": "SHIN_OMURA", "name": "Shin-Omura", "category": "normal", "x": -1498, "y": 1736},
    {"id": "ISAHAYA", "name": "Isahaya", "category": "hub", "x": -1538, "y": 1712},
    {"id": "NAGASAKI", "name": "Nagasaki", "category": "hub", "x": -1578, "y": 1688, "lat": None, "lon": None},
]


ROUTES = [
    {
        "id": "TOHOKU",
        "name": "Tohoku",
        "color": "#2d9c5b",
        "label": {"x": 1760, "y": 520},
        "stations": [
            "TOKYO", "UENO", "OMIYA", "OYAMA", "UTSUNOMIYA", "NASUSHIOBARA",
            "SHIN_SHIRAKAWA", "KORIYAMA", "FUKUSHIMA", "SHIROISHI_ZAO",
            "SENDAI_TOHOKU", "FURUKAWA", "KURIKOMA_KOGEN", "ICHINOSEKI",
            "MIZUSAWA_ESASHI", "KITAKAMI", "SHIN_HANAMAKI", "MORIOKA",
            "IWATE_NUMAKUNAI", "NINOHE", "HACHINOHE", "SHICHINOHE_TOWADA",
            "SHIN_AOMORI",
        ],
    },
    {
        "id": "HOKKAIDO",
        "name": "Hokkaido",
        "color": "#2aa7d8",
        "label": {"x": 1880, "y": 36},
        "stations": ["SHIN_AOMORI", "OKU_TSUGARU_IMABETSU", "KIKONAI", "SHIN_HAKODATE_HOKUTO"],
    },
    {
        "id": "YAMAGATA",
        "name": "Yamagata",
        "color": "#f09b20",
        "label": {"x": 1160, "y": 1210},
        "stations": [
            "TOKYO", "UENO", "OMIYA", "OYAMA", "UTSUNOMIYA", "NASUSHIOBARA",
            "SHIN_SHIRAKAWA", "KORIYAMA", "FUKUSHIMA", "YONEZAWA", "TAKAHATA",
            "AKAYU", "KAMINOYAMA_ONSEN", "YAMAGATA", "TENDO",
            "SAKURANBO_HIGASHINE", "MURAYAMA", "OISHIDA", "SHINJO",
        ],
    },
    {
        "id": "AKITA",
        "name": "Akita",
        "color": "#d54a96",
        "label": {"x": 1660, "y": 640},
        "stations": [
            "TOKYO", "UENO", "OMIYA", "OYAMA", "UTSUNOMIYA", "NASUSHIOBARA",
            "SHIN_SHIRAKAWA", "KORIYAMA", "FUKUSHIMA", "SHIROISHI_ZAO",
            "SENDAI_TOHOKU", "FURUKAWA", "KURIKOMA_KOGEN", "ICHINOSEKI",
            "MIZUSAWA_ESASHI", "KITAKAMI", "SHIN_HANAMAKI", "MORIOKA",
            "SHIZUKUISHI", "TAZAWAKO", "KAKUNODATE", "OMAGARI", "AKITA",
        ],
    },
    {
        "id": "JOETSU",
        "name": "Joetsu",
        "color": "#e65045",
        "label": {"x": 1180, "y": 1130},
        "stations": [
            "TOKYO", "UENO", "OMIYA", "KUMAGAYA", "HONJO_WASEDA", "TAKASAKI",
            "JOMO_KOGEN", "ECHIGO_YUZAWA", "URASA", "NAGAOKA",
            "TSUBAME_SANJO", "NIIGATA",
        ],
    },
    {
        "id": "GALA",
        "name": "GALA Yuzawa",
        "color": "#9aa7b5",
        "label": {"x": 1258, "y": 1218},
        "stations": ["ECHIGO_YUZAWA", "GALA_YUZAWA"],
        "dash": "8 8",
    },
    {
        "id": "HOKURIKU",
        "name": "Hokuriku",
        "color": "#2c62c9",
        "label": {"x": 720, "y": 1690},
        "stations": [
            "TOKYO", "UENO", "OMIYA", "KUMAGAYA", "HONJO_WASEDA", "TAKASAKI",
            "ANNAKA_HARUNA", "KARUIZAWA", "SAKUDAIRA", "UEDA", "NAGANO",
            "IIYAMA", "JOETSUMYOKO", "ITOIGAWA", "KUROBE_UNAZUKIONSEN",
            "TOYAMA", "SHIN_TAKAOKA", "KANAZAWA", "KOMATSU", "KAGAONSEN",
            "AWARAONSEN", "FUKUI", "ECHIZEN_TAKEFU", "TSURUGA",
        ],
    },
    {
        "id": "TOKAIDO",
        "name": "Tokaido",
        "color": "#1f4fb9",
        "label": {"x": 760, "y": 1752},
        "stations": [
            "TOKYO", "SHINAGAWA", "SHIN_YOKOHAMA", "ODAWARA", "ATAMI",
            "MISHIMA", "SHIN_FUJI", "SHIZUOKA", "KAKEGAWA", "HAMAMATSU",
            "TOYOHASHI", "MIKAWA_ANJO", "NAGOYA", "GIFU_HASHIMA", "MAIBARA",
            "KYOTO", "SHIN_OSAKA",
        ],
    },
    {
        "id": "SANYO",
        "name": "Sanyo",
        "color": "#00a0d2",
        "label": {"x": -640, "y": 1752},
        "stations": [
            "SHIN_OSAKA", "SHIN_KOBE", "NISHI_AKASHI", "HIMEJI", "AIOI",
            "OKAYAMA", "SHIN_KURASHIKI", "FUKUYAMA", "SHIN_ONOMICHI",
            "MIHARA", "HIGASHI_HIROSHIMA", "HIROSHIMA", "SHIN_IWAKUNI",
            "TOKUYAMA", "SHIN_YAMAGUCHI", "ASA", "SHIN_SHIMONOSEKI",
            "KOKURA", "HAKATA",
        ],
    },
    {
        "id": "KYUSHU",
        "name": "Kyushu",
        "color": "#d35d1f",
        "label": {"x": -1310, "y": 2088},
        "stations": [
            "HAKATA", "SHIN_TOSU", "KURUME", "CHIKUGO_FUNAGOYA",
            "SHIN_OMUTA", "SHIN_TAMANA", "KUMAMOTO", "SHIN_YATSUSHIRO",
            "SHIN_MINAMATA", "IZUMI", "SENDAI_KYUSHU", "KAGOSHIMA_CHUO",
        ],
    },
    {
        "id": "NISHI_KYUSHU",
        "name": "Nishi-Kyushu",
        "color": "#7e52b8",
        "label": {"x": -1600, "y": 1650},
        "stations": ["SHIN_TOSU", "TAKEO_ONSEN", "URESHINO_ONSEN", "SHIN_OMURA", "ISAHAYA", "NAGASAKI"],
    },
]

ROUTE_LABELS = {
    route["id"]: route["label"] for route in ROUTES
}

LABEL_LAYOUTS = {
    "TOKYO": {"dx": 20, "dy": -12},
    "UENO": {"dx": 20, "dy": -12},
    "OMIYA": {"dx": 20, "dy": -10},
    "KANAZAWA": {"dx": 16, "dy": -10},
    "NAGOYA": {"dx": 18, "dy": -10},
    "KYOTO": {"dx": 18, "dy": -10},
    "SHIN_OSAKA": {"dx": 18, "dy": -12},
    "HAKATA": {"dx": 18, "dy": -10},
    "KOKURA": {"dx": 18, "dy": -10},
    "HIROSHIMA": {"dx": 18, "dy": -10},
    "TOKUYAMA": {"dx": 18, "dy": -10},
    "SHIN_YAMAGUCHI": {"dx": 18, "dy": -10},
    "AKITA": {"dx": 18, "dy": -10},
    "NIIGATA": {"dx": 18, "dy": -10},
    "MORIOKA": {"dx": 18, "dy": -10},
    "SHIN_AOMORI": {"dx": 18, "dy": -10},
    "SHIN_HAKODATE_HOKUTO": {"dx": 18, "dy": -10},
    "SHIN_TOSU": {"dx": 18, "dy": -10},
    "KUMAMOTO": {"dx": 18, "dy": -10},
    "KAGOSHIMA_CHUO": {"dx": 18, "dy": -10},
    "NAGASAKI": {"dx": 18, "dy": -10},
}


def station_map():
    return {station["id"]: station for station in load_stations()}


def load_stations():
    if STATIONS_PATH.exists():
        return json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    return [
        {
            "id": station["id"],
            "name": station["name"],
            "names": {
                "en": station["name"],
                "ja": station.get("name"),
                "zh_hans": station["name"],
            },
            "category": station["category"],
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "geometry_seed": {"x": station["x"], "y": station["y"]},
        }
        for station in STATIONS
    ]


def load_routes():
    if ROUTES_PATH.exists():
        routes = json.loads(ROUTES_PATH.read_text(encoding="utf-8"))
        for route in routes:
            if "label" not in route and route["id"] in ROUTE_LABELS:
                route["label"] = ROUTE_LABELS[route["id"]]
        return routes
    return [
        {
            "id": route["id"],
            "name": route["name"],
            "color": route["color"],
            "station_ids": route["stations"],
            **({"dash": route["dash"]} if route.get("dash") else {}),
        }
        for route in ROUTES
    ]


def projected_points():
    latlon_stations = [station for station in load_stations() if station.get("lat") is not None and station.get("lon") is not None]
    if not latlon_stations:
        return {}

    min_lon = min(station["lon"] for station in latlon_stations)
    max_lon = max(station["lon"] for station in latlon_stations)
    min_lat = min(station["lat"] for station in latlon_stations)
    max_lat = max(station["lat"] for station in latlon_stations)

    width = 3500
    height = 2400
    left = -1500
    top = 0

    points = {}
    for station in latlon_stations:
        lon_ratio = (station["lon"] - min_lon) / (max_lon - min_lon or 1)
        lat_ratio = (station["lat"] - min_lat) / (max_lat - min_lat or 1)
        x = left + lon_ratio * width
        y = top + (1 - lat_ratio) * height
        points[station["id"]] = {"x": round(x, 2), "y": round(y, 2)}
    return points


def point_for_station(station: dict, projected: dict) -> dict:
    if station["id"] in projected:
        return projected[station["id"]]
    return {"x": station["x"], "y": station["y"]}


def path_for_route(route: dict) -> str:
    stations_by_id = station_map()
    projected = projected_points()
    points = []
    for station_id in route["station_ids"]:
        station = stations_by_id[station_id]
        point = point_for_station(
            {
                "id": station["id"],
                "x": station["geometry_seed"]["x"],
                "y": station["geometry_seed"]["y"],
            }
            | station,
            projected,
        )
        points.append(f"{point['x']},{point['y']}")
    return " ".join(points)


def route_label_rect(route: dict) -> tuple[float, float, float, float]:
    label = route["label"]
    text = route["name"]
    width = max(88, 12 * len(text) + 24)
    height = 28
    x = label["x"] - 10
    y = label["y"] - 18
    return x, y, width, height


def rects_intersect(a: tuple[float, float, float, float], b: tuple[float, float, float, float], padding: float = 0) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (
        ax2 + padding < bx1
        or bx2 + padding < ax1
        or ay2 + padding < by1
        or by2 + padding < ay1
    )


def estimate_label_box(
    station_name: str,
    anchor_x: float,
    anchor_y: float,
    dx: float,
    dy: float,
    font_size: float,
) -> tuple[float, float, float, float]:
    width = max(28, len(station_name) * font_size * 0.62)
    height = font_size + 6
    x1 = anchor_x + dx
    y2 = anchor_y + dy
    y1 = y2 - height
    x2 = x1 + width
    return (x1, y1, x2, y2)


def circle_intersects_rect(cx: float, cy: float, radius: float, rect: tuple[float, float, float, float], padding: float = 0) -> bool:
    x1, y1, x2, y2 = rect
    nearest_x = min(max(cx, x1), x2)
    nearest_y = min(max(cy, y1), y2)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return dx * dx + dy * dy <= (radius + padding) * (radius + padding)


def choose_label_layout(
    station: dict,
    point: dict,
    radius: float,
    font_size: float,
    occupied_rects: list[tuple[float, float, float, float]],
    station_circles: list[tuple[float, float, float]],
) -> tuple[float, float]:
    preferred = LABEL_LAYOUTS.get(station["id"])
    candidates = []
    if preferred:
        candidates.append((preferred["dx"], preferred["dy"]))
    candidates.extend(
        [
            (18, -6),
            (18, 16),
            (-18 - len(station["name"]) * font_size * 0.62, -6),
            (-18 - len(station["name"]) * font_size * 0.62, 16),
            (12, -18),
            (12, 26),
            (26, -18),
            (26, 26),
        ]
    )

    best = candidates[0]
    best_score = None
    for dx, dy in candidates:
        rect = estimate_label_box(station["name"], point["x"], point["y"], dx, dy, font_size)
        overlap_count = 0
        for other_rect in occupied_rects:
            if rects_intersect(rect, other_rect, padding=6):
                overlap_count += 1
        for cx, cy, cr in station_circles:
            if circle_intersects_rect(cx, cy, cr, rect, padding=6):
                overlap_count += 3
        distance_penalty = math.hypot(dx, dy) * 0.05
        score = overlap_count * 1000 + distance_penalty
        if best_score is None or score < best_score:
            best_score = score
            best = (dx, dy)
            if overlap_count == 0:
                break
    return best


def render_svg() -> str:
    width = 2600
    height = 2700
    stations = load_stations()
    routes = load_routes()
    projected = projected_points()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="-1700 -120 4400 2680" role="img" aria-labelledby="title desc">',
        '<title id="title">OniChase V2 Geometry Map</title>',
        '<desc id="desc">Data-driven Shinkansen map generated from route and station geometry.</desc>',
        "<defs>",
        "<style>",
        ".bg { fill: #efe9db; }",
        ".panel { fill: #fffdfa; stroke: #d5ccbb; stroke-width: 2; }",
        ".title { font: 700 38px Helvetica, Arial, sans-serif; fill: #17212b; }",
        ".subtitle { font: 500 18px Helvetica, Arial, sans-serif; fill: #5f6b76; }",
        ".note { font: 500 13px Helvetica, Arial, sans-serif; fill: #7a8794; }",
        ".route-back { fill: none; stroke: #ffffff; stroke-width: 16; stroke-linecap: round; stroke-linejoin: round; opacity: 0.96; }",
        ".route { fill: none; stroke-width: 9; stroke-linecap: round; stroke-linejoin: round; }",
        ".station { fill: #fffdfa; stroke: #1f2933; stroke-width: 2.2; }",
        ".hub { fill: #fffdfa; stroke: #1f2933; stroke-width: 4.4; }",
        ".station-label { font: 600 12px Helvetica, Arial, sans-serif; fill: #1f2933; paint-order: stroke; stroke: #fffdfa; stroke-width: 3.5; stroke-linejoin: round; }",
        ".hub-label { font: 700 13px Helvetica, Arial, sans-serif; fill: #1f2933; paint-order: stroke; stroke: #fffdfa; stroke-width: 4; stroke-linejoin: round; }",
        ".line-label-box { stroke: #ffffff; stroke-width: 2; rx: 14; }",
        ".line-label { font: 700 14px Helvetica, Arial, sans-serif; fill: #ffffff; letter-spacing: 0.2px; }",
        "</style>",
        "</defs>",
        '<rect class="bg" x="-1700" y="-120" width="4400" height="2680"/>',
        '<rect class="panel" x="-1650" y="-80" width="4300" height="2600" rx="30"/>',
        '<text class="title" x="-1580" y="-20">OniChase V2 Shinkansen Draft</text>',
        '<text class="subtitle" x="-1580" y="12">Data-driven nationwide map built from real station coordinates and real route order.</text>',
        '<text class="note" x="-1580" y="2460">Current pass: cleaner linework and labels over the real-coordinate geometry pipeline.</text>',
    ]

    occupied_rects = []
    for route in routes:
        occupied_rects.append(route_label_rect(route))

    for route in routes:
        dash_attr = ""
        if route.get("dash"):
            dash_attr = f' stroke-dasharray="{route["dash"]}"'
        route_points = path_for_route(route)
        parts.append(
            f'<polyline class="route-back"{dash_attr} points="{route_points}"/>'
        )
        parts.append(
            f'<polyline class="route" stroke="{route["color"]}"{dash_attr} points="{route_points}"/>'
        )
        label = route["label"]
        rx, ry, rw, rh = route_label_rect(route)
        parts.append(
            f'<rect class="line-label-box" x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{route["color"]}"/>'
        )
        parts.append(
            f'<text class="line-label" x="{label["x"]}" y="{label["y"]}">{route["name"]}</text>'
        )

    for station in stations:
        font_size = 13 if station["category"] == "hub" else 12
        point = point_for_station(
            {
                "id": station["id"],
                "x": station["geometry_seed"]["x"],
                "y": station["geometry_seed"]["y"],
            }
            | station,
            projected,
        )
        klass = "hub" if station["category"] == "hub" else "station"
        radius = 9 if station["category"] == "hub" else 6
        label_class = "hub-label" if station["category"] == "hub" else "station-label"
        station_circles = [
            (
                point_for_station(
                    {
                        "id": other["id"],
                        "x": other["geometry_seed"]["x"],
                        "y": other["geometry_seed"]["y"],
                    }
                    | other,
                    projected,
                )["x"],
                point_for_station(
                    {
                        "id": other["id"],
                        "x": other["geometry_seed"]["x"],
                        "y": other["geometry_seed"]["y"],
                    }
                    | other,
                    projected,
                )["y"],
                13 if other["category"] == "hub" else 10,
            )
            for other in stations
            if other["id"] != station["id"]
        ]
        label_dx, label_dy = choose_label_layout(station, point, radius, font_size, occupied_rects, station_circles)
        parts.append(
            f'<circle class="{klass}" cx="{point["x"]}" cy="{point["y"]}" r="{radius}"/>'
        )
        parts.append(
            f'<text class="{label_class}" x="{point["x"] + label_dx}" y="{point["y"] + label_dy}">{station["name"]}</text>'
        )
        occupied_rects.append(
            estimate_label_box(station["name"], point["x"], point["y"], label_dx, label_dy, font_size)
        )

    parts.append("</svg>")
    return "\n".join(parts)


def export_json():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATIONS_PATH.exists():
        stations_payload = []
        for station in STATIONS:
            stations_payload.append(
                {
                    "id": station["id"],
                    "name": station["name"],
                    "names": {
                        "en": station["name"],
                        "ja": station["name"],
                        "zh_hans": station["name"],
                    },
                    "category": station["category"],
                    "lat": station.get("lat"),
                    "lon": station.get("lon"),
                    "geometry_seed": {"x": station["x"], "y": station["y"]},
                }
            )
        STATIONS_PATH.write_text(
            json.dumps(stations_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if not ROUTES_PATH.exists():
        routes_payload = []
        for route in ROUTES:
            route_payload = {
                "id": route["id"],
                "name": route["name"],
                "color": route["color"],
                "station_ids": route["stations"],
            }
            if route.get("dash"):
                route_payload["dash"] = route["dash"]
            routes_payload.append(route_payload)
        ROUTES_PATH.write_text(
            json.dumps(routes_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def main():
    export_json()
    VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    (VISUALS_DIR / "shinkansen_v2_map_real_geometry.svg").write_text(
        render_svg(),
        encoding="utf-8",
    )
    print("Wrote data/shinkansen_v2_stations.json")
    print("Wrote data/shinkansen_v2_routes.json")
    print("Wrote visuals/shinkansen_v2_map_real_geometry.svg")


if __name__ == "__main__":
    main()
