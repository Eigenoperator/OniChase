#!/usr/bin/env python3
"""Append non-overlapping official airport-bus sources to the V5 bus bundle.

Official HTML/PDF parsers often produce real timetables before a GTFS feed is
available.  This augmenter only promotes a route into gameplay when every stop
can be resolved to a real coordinate and the overlap audit does not mark it as
an existing GTFS route.  Unresolved routes stay in the audit instead of being
invented on the map.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_v5_bus_gtfs_bundle import (  # noqa: E402
    airport_reference_nodes,
    build_connectors,
    haversine_meters,
    rail_reference_nodes,
    stable_slug,
)


DEFAULT_INPUT_BUNDLE = ROOT / "docs" / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_OUTPUT_BUNDLE = ROOT / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_DOCS_OUTPUT_BUNDLE = ROOT / "docs" / "data" / "v5_bus_gtfs_current_bundle.json.gz"
DEFAULT_AUDIT_OUTPUT = ROOT / "data" / "v5_official_bus_bundle_augmentation_audit.json"
DEFAULT_DOCS_AUDIT_OUTPUT = ROOT / "docs" / "data" / "v5_official_bus_bundle_augmentation_audit.json"
DEFAULT_OVERLAP_AUDIT = ROOT / "data" / "v5_official_bus_source_overlap_audit.json"
DEFAULT_MAP_BUNDLE = ROOT / "data" / "v4_gameplay_map_bundle.json.gz"
DEFAULT_AIRPORT_MAP = ROOT / "docs" / "data" / "v5_flight_map.geojson"
DEFAULT_GEOCODE_CACHE = ROOT / "data" / "v5_bus_official_cache" / "nominatim_stop_geocode_cache.json"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
AIRPORT_STOP_ALIASES = {
    "HND": ["羽田空港", "東京国際空港", "haneda airport"],
    "NRT": ["成田空港", "成田国際空港", "narita airport"],
    "KIX": ["関西空港", "関西国際空港", "kansai airport"],
    "ITM": ["大阪空港", "伊丹空港", "osaka airport", "itami airport"],
    "CTS": ["新千歳空港", "new chitose airport"],
    "TAK": ["高松空港", "takamatsu airport"],
    "ISG": ["石垣空港", "新石垣空港", "ishigaki airport"],
    "KOJ": ["鹿児島空港", "kagoshima airport"],
    "KMI": ["宮崎空港", "miyazaki airport"],
    "NGS": ["長崎空港", "nagasaki airport"],
    "KIJ": ["新潟空港", "niigata airport"],
    "UKB": ["神戸空港", "kobe airport"],
    "HKD": ["函館空港", "hakodate airport"],
    "AXT": ["秋田空港", "akita airport"],
    "MMY": ["宮古空港", "miyako airport"],
    "SHI": ["みやこ下地島空港", "下地島空港", "shimojishima airport"],
}
MANUAL_STOP_COORD_ALIASES = {
    # Nagasaki airport-bus city stops.  中央橋 coordinates are from Busmap's
    # structured BusStop geo data; the station/terminal aliases point at the
    # nearest rail station-group centroid already present in the gameplay map.
    "中央橋": {"lat": 32.7446326603, "lon": 129.875337528, "source": "busmap:busstop:227750"},
    "長崎駅前県営バスターミナル": {"aliasRailStation": "長崎駅前", "source": "rail_station_group_alias:長崎駅前"},
    "長崎駅県営bt": {"aliasRailStation": "長崎駅前", "source": "rail_station_group_alias:長崎駅前"},
    "長崎駅前(交通広場)": {"aliasRailStation": "長崎駅前", "source": "rail_station_group_alias:長崎駅前"},
    "長崎駅(交通広場)": {"aliasRailStation": "長崎駅前", "source": "rail_station_group_alias:長崎駅前"},
    "銭座町スタジアムシティ": {"aliasRailStation": "銭座町", "source": "rail_station_group_alias:銭座町"},
    "銭座町ｽﾀｼﾞｱﾑｼﾃｨ": {"aliasRailStation": "銭座町", "source": "rail_station_group_alias:銭座町"},
    "銭座町長崎スタジアムシティ": {"aliasRailStation": "銭座町", "source": "rail_station_group_alias:銭座町"},
    # KIX / KATE English stop labels, normalized to existing rail station
    # groups when the official label names a station or station bus terminal.
    "hankyusanban(osakasta)um1": {"aliasRailStation": "大阪梅田", "source": "rail_station_group_alias:大阪梅田"},
    "herbisosaka(osakasta)": {"aliasRailStation": "西梅田", "source": "rail_station_group_alias:西梅田"},
    "todojima(candeohotelsosakathetower)": {"aliasRailStation": "渡辺橋", "source": "rail_station_group_alias:渡辺橋"},
    "hotelhankyurespire(yodobashiumedatower)um9": {"aliasRailStation": "大阪梅田", "source": "rail_station_group_alias:大阪梅田"},
    "kintetsuuehommachi(2ndfloorbusterminal)": {"aliasRailStation": "大阪上本町", "source": "rail_station_group_alias:大阪上本町"},
    "shinsaibashi(hotelnikkoosaka)": {"aliasRailStation": "心斎橋", "source": "rail_station_group_alias:心斎橋"},
    "hotelentrance(infrontofjrsakurajimastation)nu8": {"aliasRailStation": "桜島", "source": "rail_station_group_alias:桜島"},
    "universalcitywalkosaka(hotelkintetsuuniversalcity)": {"aliasRailStation": "ユニバーサルシティ", "source": "rail_station_group_alias:ユニバーサルシティ"},
    "tenpozan(kaiyukan)": {"lat": 34.6549, "lon": 135.4289, "source": "manual_poi_alias:海遊館"},
    "grandprincehotelosakabayhoshinoresortsrisonareosaka": {"lat": 34.6369052, "lon": 135.4158899, "source": "nominatim_manual_cache:Grand Prince Hotel Osaka Bay"},
    "shinkobe(crowneplazakobe)kb3": {"aliasRailStation": "新神戸", "source": "rail_station_group_alias:新神戸"},
    "narastanr4": {"aliasRailStation": "奈良", "source": "rail_station_group_alias:奈良"},
    "dainihannaikoma": {"lat": 34.7054, "lon": 135.7276, "source": "official_name_alias:第二阪奈生駒"},
    "namba()oc1": {"aliasRailStation": "大阪難波", "source": "rail_station_group_alias:大阪難波"},
    "plazaosakaon1": {"aliasRailStation": "日本橋", "source": "rail_station_group_alias:日本橋"},
    "temmabashista": {"aliasRailStation": "天満橋", "source": "rail_station_group_alias:天満橋"},
    "hankyunishinomiyakitaguchi": {"aliasRailStation": "西宮北口", "source": "rail_station_group_alias:西宮北口"},
    "wakayamastawk1": {"aliasRailStation": "和歌山", "source": "rail_station_group_alias:和歌山"},
    "wakauraguchi": {"lat": 34.196199974725, "lon": 135.1697625603933, "source": "official_kate_busstop_detail:3476"},
    "nissekiiryocentermae": {"lat": 34.2204807, "lon": 135.1691241, "source": "nominatim_manual_cache:日赤医療センター前"},
    "wakayamajomae": {"lat": 34.2299109697, "lon": 135.174475088, "source": "busmap:busstop:1194311"},
    "mikimachishintori": {"lat": 34.2302036, "lon": 135.1796679, "source": "nominatim_manual_cache:三木町新通"},
    "highwaynaruto": {"aliasRailStation": "鳴門", "source": "rail_station_group_alias:鳴門"},
    "narutokoenguchi": {"aliasRailStation": "鳴門", "source": "rail_station_group_alias:鳴門"},
    "sumotots4": {"lat": 34.34289, "lon": 134.8955, "source": "manual_city_center_alias:洲本高速バスセンター"},
    "rokkoisland(kobebaysheratonhotel)": {"lat": 34.6898, "lon": 135.2698, "source": "manual_hotel_alias:Kobe Bay Sheraton"},
    # ITM / Hankyu Kanko airport-limousine stops.
    "大阪マルビル": {"lat": 34.6998856, "lon": 135.4966418, "source": "nominatim_manual_cache:大阪マルビル伊丹空港行きバス停"},
    "ハービス大阪": {"aliasRailStation": "西梅田", "source": "rail_station_group_alias:西梅田"},
    "ホテル阪神": {"lat": 34.6968767, "lon": 135.4876655, "source": "nominatim_manual_cache:ホテル阪神大阪"},
    "なんば": {"aliasRailStation": "大阪難波", "source": "rail_station_group_alias:大阪難波"},
    "jr難波駅(ocat)": {"aliasRailStation": "JR難波", "source": "rail_station_group_alias:JR難波"},
    "あべの橋駅(天王寺駅)": {"aliasRailStation": "天王寺", "source": "rail_station_group_alias:天王寺"},
    "近鉄上本町": {"aliasRailStation": "大阪上本町", "source": "rail_station_group_alias:大阪上本町"},
    "東大阪長田": {"lat": 34.6789607, "lon": 135.5927402, "source": "nominatim_manual_cache:東大阪長田駅"},
    "jr奈良": {"aliasRailStation": "奈良", "source": "rail_station_group_alias:奈良"},
    "奈良県コンベンションセンター": {"lat": 34.6833442, "lon": 135.8050634, "source": "mapfan:奈良県コンベンションセンター"},
    "大和西大寺駅南口": {"aliasRailStation": "大和西大寺", "source": "rail_station_group_alias:大和西大寺"},
    "2阪奈生駒": {"lat": 34.7054, "lon": 135.7276, "source": "official_name_alias:第二阪奈生駒"},
    "四条河原町": {"aliasRailStation": "京都河原町", "source": "rail_station_group_alias:京都河原町"},
    "久留美": {"lat": 34.8199568, "lon": 135.0052794, "source": "nominatim_manual_cache:久留美バス停"},
    "淡河": {"lat": 34.8211569, "lon": 135.1060640, "source": "nominatim_manual_cache:淡河バス停"},
    "阪神甲子園": {"aliasRailStation": "甲子園", "source": "rail_station_group_alias:甲子園"},
    "ユニバーサルスタジオジャパン": {"lat": 34.6656393, "lon": 135.4324527, "source": "nominatim_manual_cache:ユニバーサル・スタジオ・ジャパン"},
    # CTS / Hokkaido Chuo Bus English stop labels.
    "minamichitosestationminamichitosesta": {"aliasRailStation": "南千歳", "source": "rail_station_group_alias:南千歳"},
    "kita24josubwaystationkita24josubwaysta": {"aliasRailStation": "北24条", "source": "rail_station_group_alias:北24条"},
    "asabusubwaystationasabusubwaysta": {"aliasRailStation": "麻生", "source": "rail_station_group_alias:麻生"},
    "kita34jokita34josubwaysta": {"aliasRailStation": "北34条", "source": "rail_station_group_alias:北34条"},
    "oyachisubwaystaoyachisubwaysta": {"aliasRailStation": "大谷地", "source": "rail_station_group_alias:大谷地"},
    "miyanosawasubwaystationmiyanosawasubwaysta": {"aliasRailStation": "宮の沢", "source": "rail_station_group_alias:宮の沢"},
    "hassamuminamisubwaystationhassamuminamisubwaysta": {"aliasRailStation": "発寒南", "source": "rail_station_group_alias:発寒南"},
    "tsukisamuchuosubwaystationtsukisamuchuosubwaysta": {"aliasRailStation": "月寒中央", "source": "rail_station_group_alias:月寒中央"},
    "fukuzumisubwaystationfukuzumisubwaysta": {"aliasRailStation": "福住", "source": "rail_station_group_alias:福住"},
    "higashikuyakusyomaesubwaystationhigashikuyakusyomaesubwaysta": {"aliasRailStation": "東区役所前", "source": "rail_station_group_alias:東区役所前"},
    "kanjodorihigashisubwaystationkanjodorihigashisubwaysta": {"aliasRailStation": "環状通東", "source": "rail_station_group_alias:環状通東"},
    "otarustaotarusta": {"aliasRailStation": "小樽", "source": "rail_station_group_alias:小樽"},
    "sapporostationsapporosta": {"aliasRailStation": "札幌", "source": "rail_station_group_alias:札幌"},
    "nakajimaparknakajimapark": {"aliasRailStation": "中島公園", "source": "rail_station_group_alias:中島公園"},
    "susukinosusukino": {"aliasRailStation": "すすきの", "source": "rail_station_group_alias:すすきの"},
    "toyohira3jo10toyohira310": {"lat": 43.0473328, "lon": 141.3781287, "source": "nominatim_manual_cache:豊平3条10丁目"},
    "tsukisamuhigashi1jo19tsukisamuhigashi119": {"lat": 43.0112703, "lon": 141.420384, "source": "nominatim_manual_cache:月寒東1条19丁目"},
    "kiyotadanchiiriguchikiyotadanchiiriguchi": {"lat": 43.0019286, "lon": 141.4366259, "source": "nominatim_manual_cache:清田団地入口"},
    "mitsuioutletparkiriguchimitsuioutletpark_iriguchi": {"lat": 42.9764757, "lon": 141.4714105, "source": "nominatim_manual_cache:三井アウトレットパーク入口"},
    "miyanosawa1jo1miyanosawa11": {"aliasRailStation": "宮の沢", "source": "rail_station_group_alias:宮の沢"},
    "hassamu10jo2hassamu102": {"lat": 43.0905623, "lon": 141.2992136, "source": "nominatim_manual_cache:発寒10条2丁目"},
    "kita19johigashi20kita19higashi20": {"lat": 43.0874133, "lon": 141.3807361, "source": "nominatim_manual_cache:北19条東20丁目"},
    "kita24johigashi21kita24higashi21": {"lat": 43.0949833, "lon": 141.3835759, "source": "nominatim_manual_cache:北24条東21丁目"},
    "kita34johigashi26kita34higashi26": {"lat": 43.1002265, "lon": 141.3872554, "source": "nominatim_manual_cache:北34条東26丁目"},
    "hoteltorifitootarucanalomo5otaruhoteltorifitootarucanalomo5otaru": {"lat": 43.1987048, "lon": 141.0007839, "source": "nominatim_manual_cache:ホテル・トリフィート小樽運河"},
    "otarucanalterminalotaruungaterminal": {"lat": 43.1970566, "lon": 141.002288, "source": "nominatim_manual_cache:小樽運河ターミナル"},
    "authenthotelotaruauthenthotelotaru": {"lat": 43.19575, "lon": 140.9975954, "source": "nominatim_manual_cache:オーセントホテル小樽"},
    "sumiyoshijinjamaesumiyoshijinjashrine": {"lat": 43.1846128, "lon": 141.0040832, "source": "nominatim_manual_cache:住吉神社前"},
    "okusawaguchiokusawaguchi": {"lat": 43.1820019, "lon": 141.0075534, "source": "nominatim_manual_cache:奥沢口"},
    "minani3josusukinominami3josusukino": {"aliasRailStation": "すすきの", "source": "rail_station_group_alias:すすきの"},
    "hotelmontereyedelhofsapporohotelmontereyedelhof": {"lat": 43.0644021, "lon": 141.3555708, "source": "nominatim_manual_cache:ホテルモントレエーデルホフ札幌"},
    "kita35jonishi5kita35nishi5": {"lat": 43.102811, "lon": 141.3396759, "source": "nominatim_manual_cache:北35条西5丁目"},
    "shiyakushodorishiyakushodori": {"lat": 43.1923, "lon": 140.9975612, "source": "nominatim_manual_cache:市役所通"},
    # HND / Keikyu airport-bus terminal labels.
    "蘇我駅東口": {"aliasRailStation": "蘇我", "source": "rail_station_group_alias:蘇我"},
    "軽井沢駅前(北口)": {"aliasRailStation": "軽井沢", "source": "rail_station_group_alias:軽井沢"},
    "軽井沢駅(北口)": {"aliasRailStation": "軽井沢", "source": "rail_station_group_alias:軽井沢"},
    "軽井沢プリンスホテルスキー場(冬季限定)": {"lat": 36.3364101, "lon": 138.6433679, "source": "nominatim_manual_cache:軽井沢プリンスホテルスキー場"},
    "横浜駅(ycat)": {"aliasRailStation": "横浜", "source": "rail_station_group_alias:横浜"},
    "横浜駅(ｙｃａｔ)": {"aliasRailStation": "横浜", "source": "rail_station_group_alias:横浜"},
    "ﾖｺﾊﾏｸﾞﾗﾝﾄﾞｲﾝﾀｰｺﾝﾁﾈﾝﾀﾙﾎﾃﾙ(ﾊﾟｼﾌｨｺ横浜)": {"lat": 35.4577326, "lon": 139.6375026, "source": "manual_poi_alias:InterContinental Yokohama Grand"},
    "国際橋ｶｯﾌﾟﾇｰﾄﾞﾙﾐｭｰｼﾞｱﾑ前": {"lat": 35.4551301, "lon": 139.6387353, "source": "nominatim_manual_cache:国際橋・カップヌードルミュージアム前"},
    "ザカハラホテル&リゾート横浜(パシフィコ横浜ノース)": {"lat": 35.4623097, "lon": 139.6342408, "source": "nominatim_manual_cache:ザ・カハラ・ホテル＆リゾート横浜"},
    "渋谷駅(渋谷フクラス)": {"aliasRailStation": "渋谷", "source": "rail_station_group_alias:渋谷"},
    "ｊｒ千葉駅(西口)": {"aliasRailStation": "千葉", "source": "rail_station_group_alias:千葉"},
    "中央道西桂": {"aliasRailStation": "三つ峠", "source": "rail_station_group_alias:三つ峠"},
    "中央道小形山": {"lat": 35.5905243, "lon": 138.9245592, "source": "nominatim_manual_cache:中央道小形山"},
    "木更津羽鳥野バスストップ": {"lat": 35.3474710, "lon": 139.9449330, "source": "nominatim_manual_cache:木更津羽鳥野"},
    "富津浅間山バスストップ": {"lat": 35.23610934594869, "lon": 139.88811409090593, "source": "busmap:busstop:1081795"},
    # KMI / Miyazaki Kotsu airport-bus terminal labels.
    "宮崎駅": {"aliasRailStation": "宮崎", "source": "rail_station_group_alias:宮崎"},
    "西都城駅前バスセンター": {"aliasRailStation": "西都城", "source": "rail_station_group_alias:西都城"},
    "西都城駅バスセンター": {"aliasRailStation": "西都城", "source": "rail_station_group_alias:西都城"},
    "西都城駅前ｂｃ": {"aliasRailStation": "西都城", "source": "rail_station_group_alias:西都城"},
    "飫肥": {"aliasRailStation": "飫肥", "source": "rail_station_group_alias:飫肥"},
    "飫肥(日南)": {"aliasRailStation": "飫肥", "source": "rail_station_group_alias:飫肥"},
    "シーガイア": {"lat": 31.9603050, "lon": 131.4702795, "source": "nominatim_manual_cache:シーガイアコンベンションセンター"},
    "シーガイアｏｔ": {"lat": 31.9603050, "lon": 131.4702795, "source": "nominatim_manual_cache:シーガイアコンベンションセンター"},
    # KIJ / Niigata Kotsu airport-bus terminal labels.
    "新潟駅": {"aliasRailStation": "新潟", "source": "rail_station_group_alias:新潟"},
    # KOJ / Kagoshima Kotsu airport-bus stops. Coordinates are from NAVITIME
    # route pages or Busmap structured stop data for the same route corridors.
    "国分ａコープ前": {"lat": 31.73218, "lon": 130.773544, "source": "navitime_route:00077774:国分Ａコープ前"},
    "中馬場": {"lat": 31.735156, "lon": 130.768418, "source": "navitime_route:00077774:中馬場"},
    "福島団地入口": {"lat": 31.735975, "lon": 130.766869, "source": "navitime_route:00077774:福島団地入口"},
    "国分山形屋前": {"lat": 31.739516, "lon": 130.766388, "source": "navitime_route:00077774:国分山形屋前"},
    "国分駅②": {"lat": 31.743508, "lon": 130.763612, "source": "navitime_route:00077774:国分駅前"},
    "国分駅③": {"lat": 31.743508, "lon": 130.763612, "source": "navitime_route:00077774:国分駅前"},
    "国分中央高校前": {"lat": 31.74449, "lon": 130.76545, "source": "navitime_route:00077774:国分中央高校前"},
    "向花公会堂前": {"lat": 31.747153502155065, "lon": 130.76330147783673, "source": "busmap:busstop:247449"},
    "阿多石": {"lat": 31.755972, "lon": 130.762024, "source": "navitime_route:00077774:阿多石"},
    "中ノ城": {"lat": 31.759382, "lon": 130.759921, "source": "navitime_route:00077774:中ノ城"},
    "姫城温泉": {"lat": 31.761345079443924, "lon": 130.75754979092224, "source": "busmap:busstop:251638"},
    "隼人温泉病院前": {"lat": 31.765799, "lon": 130.757231, "source": "navitime_route:00077774:隼人温泉病院前"},
    "姫城ａコープ前": {"lat": 31.767667, "lon": 130.757064, "source": "navitime_route:00077774:姫城Ａコープ前"},
    "日当山小前": {"lat": 31.772077, "lon": 130.758008, "source": "navitime_route:00077774:日当山小前"},
    "日当山小北": {"lat": 31.77329, "lon": 130.758403, "source": "navitime_route:00077774:日当山小北"},
    "西光寺": {"lat": 31.774293, "lon": 130.749662, "source": "navitime_route:00077774:西光寺"},
    "西光寺③": {"lat": 31.774293, "lon": 130.749662, "source": "navitime_route:00077774:西光寺"},
    "西光寺④": {"lat": 31.774293, "lon": 130.749662, "source": "navitime_route:00077774:西光寺"},
    "鉄橋下": {"lat": 31.774082, "lon": 130.743948, "source": "navitime_route:00077774:鉄橋下"},
    "中西光寺": {"lat": 31.771794, "lon": 130.731897, "source": "navitime_route:00077774:中西光寺"},
    "垂水港": {"lat": 31.484314, "lon": 130.691872, "source": "navitime_route:00082773:垂水港"},
    "小中野": {"lat": 31.560719, "lon": 130.762596, "source": "navitime_route:00082773:小中野"},
    "宮浦宮": {"lat": 31.671403, "lon": 130.818446, "source": "navitime_route:00082773:宮浦宮"},
    "敷根": {"lat": 31.703833, "lon": 130.792074, "source": "navitime_route:00082773:敷根"},
    "八合原": {"lat": 31.571611, "lon": 131.011559, "source": "navitime_route:00083126:八合原"},
    "県改良研究所": {"lat": 31.582848, "lon": 131.005906, "source": "navitime_route:00083126:県改良研究所前"},
    "岩川": {"lat": 31.594186, "lon": 130.997661, "source": "navitime_route:00083126:岩川"},
    "笠木小前": {"lat": 31.630284879757358, "lon": 130.96644151791008, "source": "busmap:busstop:246600"},
    "飛佐入口": {"lat": 31.634734, "lon": 130.91584, "source": "navitime_route:00083126:飛佐入口"},
    "二重堀": {"lat": 31.648444, "lon": 130.897182, "source": "navitime_route:00083126:二重堀"},
    "福山高校前": {"lat": 31.666972008637476, "lon": 130.85721452931338, "source": "busmap:busstop:251739"},
    "牧之原十文字": {"lat": 31.670466, "lon": 130.848946, "source": "navitime_route:00083126:牧之原十文字"},
    "霧島市役所": {"lat": 31.740082, "lon": 130.763156, "source": "navitime_route:00083126:霧島市役所"},
    "東団地前": {"lat": 31.387724, "lon": 130.880631, "source": "navitime_route:00083098:東団地前"},
    "寿中央": {"lat": 31.386852, "lon": 130.866453, "source": "navitime_route:00083098:寿中央"},
    "鹿屋市役所前": {"lat": 31.378201, "lon": 130.853507, "source": "navitime_route:00083098:市役所前"},
    "旭原": {"lat": 31.408976, "lon": 130.881217, "source": "navitime_route:00083098:旭原"},
    "道の駅あらさの": {"lat": 31.500198, "lon": 130.924133, "source": "navitime_route:00083098:道の駅あらさの"},
    # TAK / Kotoden and Kotosan airport-bus city stops.
    "jrホテルクレメント高松": {"lat": 34.3521595, "lon": 134.0479138, "source": "nominatim_manual_cache:JRホテルクレメント高松バス停"},
    "フェリー乗り場": {"lat": 34.350014, "lon": 134.050172, "source": "manual_poi_alias:高松港フェリーのりば"},
    "県民ホール県立ミュージアム": {"lat": 34.350343, "lon": 134.050992, "source": "manual_poi_alias:レクザムホール・香川県立ミュージアム"},
    "兵庫町": {"lat": 34.34480, "lon": 134.04825, "source": "manual_city_stop_alias:高松兵庫町"},
    "県庁通り中央公園前": {"lat": 34.34168, "lon": 134.04611, "source": "manual_city_stop_alias:高松県庁通り中央公園前"},
    "栗林公園前": {"aliasRailStation": "栗林公園", "source": "rail_station_group_alias:栗林公園"},
    "ゆめタウン高松前": {"lat": 34.3169382, "lon": 134.0389990, "source": "nominatim_manual_cache:ゆめタウン高松前"},
    "香川大学附属中学校前": {"lat": 34.2991367, "lon": 134.0346724, "source": "nominatim_manual_cache:香川大学附属中学校前"},
    "オークラホテル丸亀": {"lat": 34.3068532, "lon": 133.7950996, "source": "nominatim_manual_cache:オークラホテル丸亀"},
    # UKB / Kobe airport to Tokushima labels include bilingual suffixes.
    "新神戸駅shinkobesta": {"aliasRailStation": "新神戸", "source": "rail_station_group_alias:新神戸"},
    "三宮btsannomiyabt": {"aliasRailStation": "神戸三宮", "source": "rail_station_group_alias:神戸三宮"},
    "高速舞子highwaymaiko": {"aliasRailStation": "舞子", "source": "rail_station_group_alias:舞子"},
    "鳴門公園口narutopark": {"lat": 34.22908, "lon": 134.64078, "source": "manual_poi_alias:鳴門公園口"},
    "アオアヲナルトリゾート前(※)aoawonarutoresort": {"lat": 34.2200534, "lon": 134.6329971, "source": "nominatim_manual_cache:アオアヲナルトリゾート"},
    "大塚国際美術館前(※)otsukamuseumofart": {"lat": 34.2325795, "lon": 134.6375369, "source": "nominatim_manual_cache:大塚国際美術館"},
    "高速鳴門highwaynaruto": {"aliasRailStation": "鳴門", "source": "rail_station_group_alias:鳴門"},
    "徳島大学前tokushimauniv": {"lat": 34.0779745, "lon": 134.5590655, "source": "nominatim_manual_cache:徳島大学前"},
    "徳島駅tokushimasta": {"aliasRailStation": "徳島", "source": "rail_station_group_alias:徳島"},
}
SCOPED_MANUAL_STOP_COORD_ALIASES = {
    # Route-scoped because "一宮" is highly ambiguous nationwide.  On the
    # HND/Katsunuma official source it is the Yamanashi expressway stop between
    # 石和 and 勝沼, matching 中央道甲斐一宮.
    ("HND", "airport_h-katsunuma", "一宮"): {
        "lat": 35.636703,
        "lon": 138.690811,
        "source": "bustein_manual_cache:中央道甲斐一宮",
    },
}


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_time_seconds(value: Any) -> int | None:
    text = str(value or "").strip().replace("：", ":")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60


def normalize_stop_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("　", " ")
    text = re.sub(r"\s+", "", text)
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"[・･,，.。/／\\-]", "", text)
    text = text.replace("バスターミナル", "bt")
    text = text.replace("ターミナル", "terminal")
    text = text.replace("第1", "1").replace("第2", "2")
    text = text.replace("第一", "1").replace("第二", "2")
    text = text.replace("駅前", "駅")
    if len(text) > 2 and text.endswith("駅"):
        text = text[:-1]
    return text


def compact_latin_label(value: str) -> str:
    text = value.lower().replace("sta.", "station").replace("sta", "station")
    return re.sub(r"[^a-z0-9]", "", text)


def simplified_stop_queries(stop_name: str) -> list[str]:
    queries = [stop_name]
    tokens = stop_name.split()
    for index in range(1, len(tokens)):
        prefix = " ".join(tokens[:index])
        suffix = " ".join(tokens[index:])
        prefix_key = compact_latin_label(prefix)
        suffix_key = compact_latin_label(suffix)
        if len(prefix_key) >= 6 and len(suffix_key) >= 6 and (prefix_key == suffix_key or suffix_key.startswith(prefix_key)):
            queries.append(prefix)
            break
    return list(dict.fromkeys(query for query in queries if query.strip()))


def fallback_route_code(route: dict[str, Any]) -> str:
    code = str(route.get("routeCode") or "").strip()
    if code:
        return code
    route_number = str(route.get("routeNumber") or "").strip()
    direction = str(route.get("direction") or "").strip()
    if route_number and direction:
        return f"{route_number}_{direction}"
    if route_number:
        return route_number
    route_name = str(route.get("routeName") or "").strip()
    if route_name and direction:
        return f"{stable_slug(route_name)}_{stable_slug(direction)}"
    return ""


def source_ref(path: Path, route: dict[str, Any]) -> dict[str, Any]:
    route_code = fallback_route_code(route)
    return {
        "sourceKind": route.get("sourceKind") or "official_airport_bus_source",
        "sourcePath": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "operatorName": route.get("operatorName") or "",
        "airportIata": route.get("airportIata") or "",
        "routeCode": route_code,
        "routeName": route.get("routeName") or "",
        "sourceUrl": route.get("sourceUrl") or "",
        "cachePath": route.get("cachePath") or "",
    }


def route_key(path: Path, route: dict[str, Any]) -> tuple[str, str]:
    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return rel, str(fallback_route_code(route) or route.get("routeName") or "")


def load_overlap_status(path: Path) -> dict[tuple[str, str], str]:
    if not path.exists():
        return {}
    data = read_json(path)
    statuses = {}
    for row in data.get("routes") or []:
        statuses[(str(row.get("sourcePath") or ""), str(row.get("routeCode") or row.get("routeName") or ""))] = str(row.get("status") or "")
    return statuses


def load_airport_coords(path: Path) -> dict[str, dict[str, Any]]:
    coords = {}
    for node in airport_reference_nodes(path):
        iata = node["id"].split(":", 1)[-1]
        coords[iata] = node
    return coords


def build_name_index(nodes: list[dict[str, Any]], *, id_key: str = "id") -> dict[str, list[dict[str, Any]]]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        name = node.get("name")
        lat = node.get("lat")
        lon = node.get("lon")
        if not name or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        item = {
            "id": node.get(id_key) or node.get("id"),
            "name": name,
            "lat": float(lat),
            "lon": float(lon),
            "source": node.get("targetMode") or node.get("source") or "reference_node",
        }
        by_name[normalize_stop_name(name)].append(item)
    return by_name


def bus_stop_reference_nodes(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = []
    for stop in bundle.get("stops") or []:
        lat = stop.get("lat")
        lon = stop.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        nodes.append(
            {
                "id": stop.get("busStopId"),
                "name": stop.get("name") or "",
                "lat": float(lat),
                "lon": float(lon),
                "source": "existing_bus_gtfs_stop",
            }
        )
    return nodes


def nearest_to_anchor(candidates: list[dict[str, Any]], anchor: dict[str, Any] | None, max_meters: int) -> dict[str, Any] | None:
    if not candidates:
        return None
    if not anchor:
        return candidates[0]
    ranked = sorted(
        ((haversine_meters(candidate, anchor), candidate) for candidate in candidates),
        key=lambda item: item[0],
    )
    if ranked and ranked[0][0] <= max_meters:
        return ranked[0][1] | {"resolvedDistanceToAirportMeters": int(round(ranked[0][0]))}
    return None


def airport_stop_match(stop_name: str, route_airport_iata: str, airports: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    normalized = normalize_stop_name(stop_name)
    for iata, aliases in AIRPORT_STOP_ALIASES.items():
        if any(normalize_stop_name(alias) in normalized for alias in aliases):
            airport = airports.get(iata)
            if airport:
                return {
                    "name": stop_name,
                    "lat": airport["lat"],
                    "lon": airport["lon"],
                    "source": f"airport_iata_alias:{iata}",
                }
    if route_airport_iata and "空港" in str(stop_name):
        airport = airports.get(route_airport_iata)
        if airport:
            return {
                "name": stop_name,
                "lat": airport["lat"],
                "lon": airport["lon"],
                "source": f"route_airport_iata:{route_airport_iata}",
            }
    return None


def load_geocode_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def geocode_stop(
    stop_name: str,
    *,
    cache: dict[str, Any],
    cache_path: Path,
    anchor: dict[str, Any] | None,
    max_meters: int,
    enabled: bool,
    sleep_seconds: float,
) -> dict[str, Any] | None:
    key = normalize_stop_name(stop_name)
    cached = cache.get(key)
    if cached:
        if cached.get("status") == "ok":
            candidate = {"name": stop_name, "lat": float(cached["lat"]), "lon": float(cached["lon"]), "source": "nominatim_cache"}
            if not anchor or haversine_meters(candidate, anchor) <= max_meters:
                return candidate
        if not enabled:
            return None
    if not enabled:
        return None
    selected = None
    attempted_queries = []
    for query in simplified_stop_queries(stop_name):
        attempted_queries.append(query)
        params = urllib.parse.urlencode({"q": f"{query}, 日本", "format": "jsonv2", "limit": "5", "countrycodes": "jp"})
        request = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"User-Agent": "OniChase-v5-official-bus-coordinate-resolver/0.1"},
        )
        time.sleep(sleep_seconds)
        try:
            rows = json.load(urllib.request.urlopen(request, timeout=20))
        except Exception as exc:  # noqa: BLE001
            cache[key] = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "queries": attempted_queries}
            write_json(cache_path, cache)
            return None
        candidates = []
        for row in rows:
            try:
                candidates.append(
                    {
                        "name": stop_name,
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "source": "nominatim_openstreetmap",
                        "displayName": row.get("display_name") or "",
                        "query": query,
                    }
                )
            except (KeyError, ValueError, TypeError):
                continue
        selected = nearest_to_anchor(candidates, anchor, max_meters)
        if selected:
            break
    if selected:
        cache[key] = {
            "status": "ok",
            "lat": selected["lat"],
            "lon": selected["lon"],
            "displayName": selected.get("displayName") or "",
            "query": selected.get("query") or "",
            "resolvedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    else:
        cache[key] = {"status": "not_found_or_out_of_range", "queries": attempted_queries, "resolvedAt": datetime.now(UTC).isoformat(timespec="seconds")}
    write_json(cache_path, cache)
    return selected


class StopResolver:
    def __init__(
        self,
        *,
        existing_bundle: dict[str, Any],
        rail_nodes: list[dict[str, Any]],
        airports: dict[str, dict[str, Any]],
        geocode_cache: dict[str, Any],
        geocode_cache_path: Path,
        geocode_missing: bool,
        geocode_sleep_seconds: float,
        max_anchor_meters: int,
    ) -> None:
        self.airports = airports
        self.bus_index = build_name_index(bus_stop_reference_nodes(existing_bundle))
        self.rail_index = build_name_index(rail_nodes)
        self.rail_nodes_by_name = {
            normalize_stop_name(node.get("name")): node
            for node in rail_nodes
            if node.get("name") and isinstance(node.get("lat"), (int, float)) and isinstance(node.get("lon"), (int, float))
        }
        self.geocode_cache = geocode_cache
        self.geocode_cache_path = geocode_cache_path
        self.geocode_missing = geocode_missing
        self.geocode_sleep_seconds = geocode_sleep_seconds
        self.max_anchor_meters = max_anchor_meters
        self.created: dict[str, dict[str, Any]] = {}
        self.audit_counts = Counter()

    def resolve(self, stop_name: str, route_airport_iata: str, route_code: str = "") -> dict[str, Any] | None:
        name_key = normalize_stop_name(stop_name)
        airport_anchor = self.airports.get(route_airport_iata)
        scoped = SCOPED_MANUAL_STOP_COORD_ALIASES.get((route_airport_iata, route_code, name_key))
        if scoped and isinstance(scoped.get("lat"), (int, float)) and isinstance(scoped.get("lon"), (int, float)):
            self.audit_counts[scoped["source"]] += 1
            return {
                "name": stop_name,
                "lat": float(scoped["lat"]),
                "lon": float(scoped["lon"]),
                "source": scoped["source"],
            }
        manual = MANUAL_STOP_COORD_ALIASES.get(name_key)
        if manual:
            if manual.get("aliasRailStation"):
                rail_node = self.rail_nodes_by_name.get(normalize_stop_name(manual["aliasRailStation"]))
                if rail_node:
                    self.audit_counts[manual["source"]] += 1
                    return {
                        "name": stop_name,
                        "lat": float(rail_node["lat"]),
                        "lon": float(rail_node["lon"]),
                        "source": manual["source"],
                    }
            elif isinstance(manual.get("lat"), (int, float)) and isinstance(manual.get("lon"), (int, float)):
                self.audit_counts[manual["source"]] += 1
                return {
                    "name": stop_name,
                    "lat": float(manual["lat"]),
                    "lon": float(manual["lon"]),
                    "source": manual["source"],
                }
        airport_match = airport_stop_match(stop_name, route_airport_iata, self.airports)
        if airport_match:
            self.audit_counts[airport_match["source"]] += 1
            return airport_match
        bus_match = nearest_to_anchor(self.bus_index.get(name_key, []), airport_anchor, self.max_anchor_meters)
        if bus_match:
            self.audit_counts["existing_bus_gtfs_stop"] += 1
            return bus_match
        rail_match = nearest_to_anchor(self.rail_index.get(name_key, []), airport_anchor, self.max_anchor_meters)
        if rail_match:
            self.audit_counts["rail_station_group"] += 1
            return rail_match
        geocoded = geocode_stop(
            stop_name,
            cache=self.geocode_cache,
            cache_path=self.geocode_cache_path,
            anchor=airport_anchor,
            max_meters=self.max_anchor_meters,
            enabled=self.geocode_missing,
            sleep_seconds=self.geocode_sleep_seconds,
        )
        if geocoded:
            self.audit_counts[geocoded["source"]] += 1
            return geocoded
        self.audit_counts["unresolved"] += 1
        return None


def flatten_route_trips(route: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trip in route.get("trips") or []:
        rows.append(trip)
    for direction in route.get("directions") or []:
        for trip in direction.get("trips") or []:
            merged = dict(trip)
            merged.setdefault("direction", direction.get("direction"))
            merged.setdefault("serviceStart", direction.get("serviceStart"))
            merged.setdefault("serviceEnd", direction.get("serviceEnd"))
            rows.append(merged)
    for table_index, timetable in enumerate(route.get("timetables") or [], start=1):
        for trip in timetable.get("trips") or []:
            merged = dict(trip)
            merged.setdefault("sourceTableIndex", table_index)
            merged.setdefault("sourceTableUrl", timetable.get("tableUrl") or "")
            rows.append(merged)
    return rows


def route_stop_coordinate_index(route: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for stop in route.get("busStops") or []:
        name = str(stop.get("name") or "").strip()
        lat = stop.get("lat")
        lon = stop.get("lon")
        if name and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            index[normalize_stop_name(name)] = {"name": name, "lat": float(lat), "lon": float(lon), "source": "official_route_stop_coordinate"}
    for timetable in route.get("timetables") or []:
        for stop in timetable.get("stops") or []:
            name = str(stop.get("name") or "").strip()
            lat = stop.get("lat")
            lon = stop.get("lon")
            if name and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                index[normalize_stop_name(name)] = {"name": name, "lat": float(lat), "lon": float(lon), "source": "official_timetable_stop_coordinate"}
    return index


def trip_time_bounds(trip: dict[str, Any]) -> tuple[int | None, int | None]:
    times = [parse_time_seconds(item.get("time")) for item in trip.get("stopTimes") or []]
    times = [item for item in times if item is not None]
    if not times:
        return None, None
    return min(times), max(times)


def normalize_service_days(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        days = tuple(day for day in DAYS if day in set(str(item) for item in value))
        if days:
            return days
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"weekday", "weekdays"}:
            return ("monday", "tuesday", "wednesday", "thursday", "friday")
        if lowered in {"weekend", "weekends", "holiday", "holidays"}:
            return ("saturday", "sunday")
        if lowered in {"daily", "all"}:
            return tuple(DAYS)
    return tuple(DAYS)


def make_service_calendar_id(feed_key: str, service_start: str, service_end: str, service_days: tuple[str, ...]) -> str:
    day_key = "".join(day[:2] for day in service_days)
    return f"bus:calendar:official:{feed_key}:{service_start}:{service_end}:{day_key}"


def append_official_route(
    bundle: dict[str, Any],
    *,
    path: Path,
    route: dict[str, Any],
    resolver: StopResolver,
    service_date: str,
    max_unresolved_stops: int,
) -> dict[str, Any]:
    trips = flatten_route_trips(route)
    if not trips:
        return {"status": "skipped_no_trips", "tripCount": 0, "routeCode": fallback_route_code(route), "routeName": route.get("routeName")}
    route_code = fallback_route_code(route)
    feed_key = stable_slug("official_airport_bus", path.name, route_code or route.get("routeName"))
    route_id = f"bus:route:official:{feed_key}"
    if any(existing.get("busRouteId") == route_id for existing in bundle.get("routes") or []):
        return {
            "status": "skipped_existing_official_route",
            "operatorName": route.get("operatorName") or "",
            "airportIata": route.get("airportIata") or "",
            "routeCode": route_code,
            "routeName": route.get("routeName") or "",
            "tripCount": len(trips),
        }

    route_airport = str(route.get("airportIata") or "")
    source_coords = route_stop_coordinate_index(route)
    all_stop_names = []
    for trip in trips:
        for item in trip.get("stopTimes") or []:
            name = str(item.get("stopName") or "").strip()
            if name and name not in all_stop_names:
                all_stop_names.append(name)

    resolved: dict[str, dict[str, Any]] = {}
    unresolved = []
    for name in all_stop_names:
        node = source_coords.get(normalize_stop_name(name)) or resolver.resolve(name, route_airport, route_code)
        if node:
            resolved[name] = node
        else:
            unresolved.append(name)

    if len(all_stop_names) < 2:
        return {
            "status": "skipped_no_complete_stop_sequence",
            "operatorName": route.get("operatorName") or "",
            "airportIata": route_airport,
            "routeCode": route_code,
            "routeName": route.get("routeName") or "",
            "tripCount": len(trips),
            "stopCount": len(all_stop_names),
        }

    if len(unresolved) > max_unresolved_stops:
        return {
            "status": "skipped_unresolved_stop_coordinates",
            "operatorName": route.get("operatorName") or "",
            "airportIata": route_airport,
            "routeCode": route_code,
            "routeName": route.get("routeName") or "",
            "tripCount": len(trips),
            "stopCount": len(all_stop_names),
            "unresolvedStopNames": unresolved,
        }

    valid_trips: list[dict[str, Any]] = []
    skipped_limited = 0
    skipped_incomplete = 0
    for trip in trips:
        if trip.get("limitedOperationMarks"):
            skipped_limited += 1
            continue
        stop_rows = []
        for item in trip.get("stopTimes") or []:
            name = str(item.get("stopName") or "").strip()
            seconds = parse_time_seconds(item.get("time"))
            if seconds is None or name not in resolved:
                continue
            stop_rows.append({"stopName": name, "seconds": seconds})
        if len(stop_rows) < 2:
            skipped_incomplete += 1
            continue
        valid_trips.append({"trip": trip, "stopRows": stop_rows})
    if not valid_trips:
        return {
            "status": "skipped_no_complete_trip_stop_times",
            "operatorName": route.get("operatorName") or "",
            "airportIata": route_airport,
            "routeCode": route_code,
            "routeName": route.get("routeName") or "",
            "tripCount": len(trips),
            "stopCount": len(all_stop_names),
            "skippedLimitedOperationTripCount": skipped_limited,
            "skippedIncompleteTripCount": skipped_incomplete,
        }

    ref = source_ref(path, route)
    agency_id = f"bus:agency:official:{feed_key}"
    adult_fare = route.get("adultFareYen")

    bundle["agencies"].append(
        {
            "busAgencyId": agency_id,
            "sourceAgencyId": route.get("operatorName") or feed_key,
            "agencyName": route.get("operatorName") or "",
            "agencyUrl": route.get("sourceUrl") or "",
            "agencyTimezone": "Asia/Tokyo",
            "agencyLang": "ja",
            "sourceRefs": [ref],
        }
    )
    for name, node in resolved.items():
        stop_id = f"bus:stop:official:{feed_key}:{hashlib.sha1(name.encode('utf-8')).hexdigest()[:12]}"
        resolver.created[name] = {
            "busStopId": stop_id,
            "sourceStopId": name,
            "name": name,
            "lat": node["lat"],
            "lon": node["lon"],
            "locationType": 0,
            "parentBusStopId": None,
            "platformCode": "",
            "wheelchairBoarding": None,
            "sourceRefs": [ref | {"coordinateSource": node.get("source") or ""}],
        }
        bundle["stops"].append(resolver.created[name])

    bundle["routes"].append(
        {
            "busRouteId": route_id,
            "sourceRouteId": route_code or route.get("routeName") or feed_key,
            "busAgencyId": agency_id,
            "agencyName": route.get("operatorName") or "",
            "routeShortName": route_code,
            "routeLongName": route.get("routeName") or "",
            "routeDesc": route.get("sourceUrl") or "",
            "routeType": 3,
            "serviceClass": "bus_airport",
            "routeColor": "2c7be5",
            "routeTextColor": "ffffff",
            "sourceRefs": [ref],
        }
    )

    calendars_seen = set()
    appended_trips = 0
    appended_stop_times = 0
    for index, valid_trip in enumerate(valid_trips, start=1):
        trip = valid_trip["trip"]
        start = str(trip.get("serviceStart") or route.get("serviceStart") or service_date).replace("-", "")
        end = str(trip.get("serviceEnd") or route.get("serviceEnd") or "20270331").replace("-", "")
        service_days = normalize_service_days(trip.get("serviceDays") or route.get("serviceDays"))
        service_id = make_service_calendar_id(feed_key, start, end, service_days)
        if service_id not in calendars_seen:
            calendars_seen.add(service_id)
            bundle["calendars"].append(
                {
                    "busServiceCalendarId": service_id,
                    "rowKind": "calendar",
                    "sourceServiceId": f"official:{feed_key}:{start}:{end}",
                    **{day: 1 if day in service_days else 0 for day in DAYS},
                    "startDate": start,
                    "endDate": end,
                }
            )
        trip_id = f"bus:trip:official:{feed_key}:{index:04d}"
        stop_rows = valid_trip["stopRows"]
        seconds_values = [row["seconds"] for row in stop_rows]
        first, last = min(seconds_values), max(seconds_values)
        if first is None or last is None:
            continue
        bundle["trips"].append(
            {
                "busTripId": trip_id,
                "sourceTripId": trip.get("tripId") or f"{feed_key}:{index}",
                "busRouteId": route_id,
                "busServiceCalendarId": service_id,
                "sourceServiceId": f"official:{feed_key}:{start}:{end}",
                "tripHeadsign": trip.get("direction") or "",
                "directionId": 1 if str(trip.get("direction") or "").startswith("from") else 0,
                "blockId": "",
                "busShapeId": None,
                "wheelchairAccessible": None,
                "bikesAllowed": None,
                "serviceClass": "bus_airport",
            }
        )
        appended_trips += 1
        seq = 0
        for item in stop_rows:
            name = item["stopName"]
            seconds = item["seconds"]
            seq += 1
            bundle["stopTimes"].append(
                {
                    "busTripId": trip_id,
                    "busStopId": resolver.created[name]["busStopId"],
                    "arrivalTimeSec": seconds,
                    "departureTimeSec": seconds,
                    "stopSequence": seq,
                    "stopHeadsign": "",
                    "pickupType": None,
                    "dropOffType": None,
                    "shapeDistTraveled": None,
                    "timepoint": 1,
                }
            )
            appended_stop_times += 1

    if adult_fare:
        fare_id = f"bus:fare:official:{feed_key}:adult"
        bundle["fareAttributes"].append(
            {
                "busFareId": fare_id,
                "sourceFareId": "adult",
                "price": int(adult_fare),
                "currencyType": "JPY",
                "paymentMethod": 0,
                "transfers": 0,
                "transferDurationSec": None,
            }
        )
        bundle["fareRules"].append({"busFareId": fare_id, "busRouteId": route_id, "originId": "", "destinationId": "", "containsId": ""})

    return {
        "status": "appended",
        "operatorName": route.get("operatorName") or "",
        "airportIata": route_airport,
        "routeCode": route_code,
        "routeName": route.get("routeName") or "",
        "sourcePath": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "stopCount": len(resolved),
        "tripCount": appended_trips,
        "stopTimeCount": appended_stop_times,
        "skippedLimitedOperationTripCount": skipped_limited,
        "skippedIncompleteTripCount": skipped_incomplete,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-bundle", type=Path, default=DEFAULT_INPUT_BUNDLE)
    parser.add_argument("--output-bundle", type=Path, default=DEFAULT_OUTPUT_BUNDLE)
    parser.add_argument("--docs-output-bundle", type=Path, default=DEFAULT_DOCS_OUTPUT_BUNDLE)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--docs-audit-output", type=Path, default=DEFAULT_DOCS_AUDIT_OUTPUT)
    parser.add_argument("--overlap-audit", type=Path, default=DEFAULT_OVERLAP_AUDIT)
    parser.add_argument("--map-bundle", type=Path, default=DEFAULT_MAP_BUNDLE)
    parser.add_argument("--airport-map", type=Path, default=DEFAULT_AIRPORT_MAP)
    parser.add_argument("--geocode-cache", type=Path, default=DEFAULT_GEOCODE_CACHE)
    parser.add_argument("--source", action="append", type=Path, default=[])
    parser.add_argument("--service-date", default="20260516")
    parser.add_argument("--geocode-missing", action="store_true")
    parser.add_argument("--geocode-sleep-seconds", type=float, default=1.0)
    parser.add_argument("--max-anchor-meters", type=int, default=250_000)
    parser.add_argument("--max-unresolved-stops", type=int, default=0)
    parser.add_argument("--max-connector-meters", type=int, default=2000)
    parser.add_argument("--max-rail-connectors-per-stop", type=int, default=12)
    parser.add_argument("--max-airport-connectors-per-stop", type=int, default=4)
    args = parser.parse_args()

    bundle = read_json(args.input_bundle)
    before_summary = {key: len(bundle.get(key) or []) for key in ("agencies", "stops", "routes", "trips", "stopTimes", "calendars", "fareAttributes", "fareRules")}
    existing_connectors = list(bundle.get("walkingConnectors") or [])
    overlap_status = load_overlap_status(args.overlap_audit)
    airports = load_airport_coords(args.airport_map)
    rail_nodes = rail_reference_nodes(args.map_bundle)
    geocode_cache = load_geocode_cache(args.geocode_cache)
    resolver = StopResolver(
        existing_bundle=bundle,
        rail_nodes=rail_nodes,
        airports=airports,
        geocode_cache=geocode_cache,
        geocode_cache_path=args.geocode_cache,
        geocode_missing=args.geocode_missing,
        geocode_sleep_seconds=args.geocode_sleep_seconds,
        max_anchor_meters=args.max_anchor_meters,
    )

    source_paths = args.source or sorted(ROOT.glob("data/v5_*official*_bus_source.json")) + sorted(ROOT.glob("data/v5_kagoshima_airport_official_bus_tables.json"))
    route_audits = []
    for path in source_paths:
        if not path.exists():
            route_audits.append({"sourcePath": str(path), "status": "source_missing"})
            continue
        data = read_json(path)
        for route in data.get("routes") or []:
            route = dict(route)
            for field in ("sourceKind", "operatorName", "airportIata"):
                if not route.get(field) and data.get(field):
                    route[field] = data[field]
            key = route_key(path, route)
            status = overlap_status.get(key)
            if status == "possible_gtfs_overlap":
                route_audits.append(
                    {
                        "status": "skipped_possible_gtfs_overlap",
                        "sourcePath": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                        "routeCode": route.get("routeCode") or "",
                        "routeName": route.get("routeName") or "",
                    }
                )
                continue
            route_audits.append(
                append_official_route(
                    bundle,
                    path=path,
                    route=route,
                    resolver=resolver,
                    service_date=args.service_date,
                    max_unresolved_stops=args.max_unresolved_stops,
                )
            )

    new_stops = (bundle.get("stops") or [])[before_summary["stops"] :]
    new_connectors, connector_summary = build_connectors(
        new_stops,
        rail_nodes=rail_nodes,
        airport_nodes=list(airports.values()),
        max_distance_meters=args.max_connector_meters,
        max_rail_per_stop=args.max_rail_connectors_per_stop,
        max_airport_per_stop=args.max_airport_connectors_per_stop,
    )
    connector_summary["existingConnectorCountPreserved"] = len(existing_connectors)
    connector_summary["newOfficialConnectorCount"] = len(new_connectors)
    bundle["walkingConnectors"] = existing_connectors + new_connectors
    bundle["generatedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    bundle.setdefault("rules", {})["officialSourceAugmentationPolicy"] = (
        "Non-overlapping official airport-bus HTML/PDF sources are appended only when every stop has a resolved real coordinate. "
        "Routes flagged as possible GTFS overlap are skipped until replacement is explicit."
    )
    bundle.setdefault("summary", {})["officialAugmentation"] = {
        "routeStatusCounts": dict(sorted(Counter(row.get("status") for row in route_audits).items())),
        "coordinateResolutionCounts": dict(sorted(resolver.audit_counts.items())),
        "connectorSummary": connector_summary,
    }

    after_summary = {key: len(bundle.get(key) or []) for key in ("agencies", "stops", "routes", "trips", "stopTimes", "calendars", "fareAttributes", "fareRules")}
    audit = {
        "schemaVersion": "v5_official_bus_bundle_augmentation_audit_v1",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourceBundle": str(args.input_bundle),
        "before": before_summary,
        "after": after_summary,
        "delta": {key: after_summary[key] - before_summary[key] for key in before_summary},
        "summary": bundle["summary"]["officialAugmentation"],
        "routeAudits": route_audits,
    }
    write_json(args.output_bundle, bundle)
    write_json(args.docs_output_bundle, bundle)
    write_json(args.audit_output, audit)
    write_json(args.docs_audit_output, audit)
    print(json.dumps(audit["summary"] | {"delta": audit["delta"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
