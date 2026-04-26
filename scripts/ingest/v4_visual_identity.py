from __future__ import annotations

import colorsys
import hashlib


OPERATOR_COLORS = {
    "jr_hokkaido": "#2CB3C9",
    "jr_east": "#249D55",
    "jr_central": "#F77321",
    "jr_west": "#2369C9",
    "jr_shikoku": "#2F7D32",
    "jr_kyushu": "#D81E24",
    "tokyo_metro": "#00A7DB",
    "toei": "#B51E82",
    "keikyu": "#E60012",
    "keio": "#DD0077",
    "keisei": "#005AAA",
    "odakyu": "#0072BC",
    "seibu": "#00A651",
    "tokyu": "#DA0442",
    "tobu": "#0F5CA8",
}


LINE_COLORS_BY_OPERATOR_LINE = {
    ("jr_central", "東海道新幹線"): "#1F78FF",
    ("jr_central", "東海道線"): "#F28E1C",
    ("jr_east", "上越新幹線"): "#E65045",
    ("jr_east", "上越線"): "#00A7E3",
    ("jr_east", "両毛線"): "#E49F00",
    ("jr_east", "中央線"): "#F15A24",
    ("jr_east", "京葉線"): "#C62828",
    ("jr_east", "伊東線"): "#319041",
    ("jr_east", "内房線"): "#00AFCC",
    ("jr_east", "北陸新幹線"): "#2C62C9",
    ("jr_east", "外房線"): "#D9352A",
    ("jr_east", "山手線"): "#88C840",
    ("jr_east", "川越線"): "#0099CC",
    ("jr_east", "常磐線"): "#22A6B3",
    ("jr_east", "成田線"): "#339966",
    ("jr_east", "東北新幹線"): "#2D9C5B",
    ("jr_east", "東北線"): "#3AA76D",
    ("jr_east", "東海道線"): "#F28E1C",
    ("jr_east", "東金線"): "#E48E00",
    ("jr_east", "根岸線"): "#00BCD4",
    ("jr_east", "横須賀線"): "#2F4CA0",
    ("jr_east", "武蔵野線"): "#FF6F00",
    ("jr_east", "総武線"): "#F4C300",
    ("jr_east", "赤羽線"): "#0099CC",
    ("jr_east", "青梅線"): "#EB5A28",
    ("jr_east", "高崎線"): "#F28E1C",
    ("jr_east", "鹿島線"): "#6F4B3E",
    ("jr_hokkaido", "北海道新幹線"): "#3F8BD8",
    ("jr_kyushu", "九州新幹線"): "#DE4B39",
    ("jr_kyushu", "西九州新幹線"): "#7C4DFF",
    ("jr_west", "北陸新幹線"): "#2C62C9",
    ("jr_west", "山陽新幹線"): "#1263D6",
    ("keikyu", "久里浜線"): "#D63339",
    ("keikyu", "大師線"): "#D63339",
    ("keikyu", "本線"): "#D63339",
    ("keikyu", "空港線"): "#D63339",
    ("keikyu", "逗子線"): "#D63339",
    ("keio", "井の頭線"): "#F18A00",
    ("keio", "京王線"): "#F18A00",
    ("keio", "動物園線"): "#F18A00",
    ("keio", "相模原線"): "#F18A00",
    ("keio", "競馬場線"): "#F18A00",
    ("keio", "高尾線"): "#F18A00",
    ("keisei", "千原線"): "#2457C5",
    ("keisei", "千葉線"): "#2457C5",
    ("keisei", "成田空港線"): "#2457C5",
    ("keisei", "押上線"): "#2457C5",
    ("keisei", "本線"): "#2457C5",
    ("keisei", "東成田線"): "#2457C5",
    ("keisei", "金町線"): "#2457C5",
    ("odakyu", "多摩線"): "#2B78D0",
    ("odakyu", "小田原線"): "#2B78D0",
    ("odakyu", "江ノ島線"): "#2B78D0",
    ("rinkai", "臨海副都心線"): "#1F5AA6",
    ("saitama_railway", "埼玉高速鉄道線"): "#00A6E9",
    ("seibu", "国分寺線"): "#00A15F",
    ("seibu", "多摩川線"): "#00A15F",
    ("seibu", "多摩湖線"): "#00A15F",
    ("seibu", "山口線"): "#00A15F",
    ("seibu", "拝島線"): "#00A15F",
    ("seibu", "新宿線"): "#00A15F",
    ("seibu", "池袋線"): "#00A15F",
    ("seibu", "狭山線"): "#00A15F",
    ("seibu", "西武園線"): "#00A15F",
    ("seibu", "西武有楽町線"): "#00A15F",
    ("seibu", "西武秩父線"): "#00A15F",
    ("seibu", "豊島線"): "#00A15F",
    ("tama_monorail", "多摩都市モノレール線"): "#54C0D8",
    ("tobu", "亀戸線"): "#1F78FF",
    ("tobu", "伊勢崎線"): "#1F78FF",
    ("tobu", "佐野線"): "#1F78FF",
    ("tobu", "大師線"): "#1F78FF",
    ("tobu", "宇都宮線"): "#1F78FF",
    ("tobu", "小泉線"): "#1F78FF",
    ("tobu", "日光線"): "#1F78FF",
    ("tobu", "東上本線"): "#1F78FF",
    ("tobu", "桐生線"): "#1F78FF",
    ("tobu", "越生線"): "#1F78FF",
    ("tobu", "野田線"): "#1F78FF",
    ("tobu", "鬼怒川線"): "#1F78FF",
    ("toei", "10号線新宿線"): "#6BBD45",
    ("toei", "12号線大江戸線"): "#B6007A",
    ("toei", "1号線浅草線"): "#EC6E65",
    ("toei", "6号線三田線"): "#0079C2",
    ("toei", "日暮里・舎人ライナー"): "#E86F2D",
    ("toei", "荒川線"): "#8B4C39",
    ("tokyo_metro", "11号線半蔵門線"): "#9B7CB6",
    ("tokyo_metro", "13号線副都心線"): "#BB641D",
    ("tokyo_metro", "2号線日比谷線"): "#9CAEB7",
    ("tokyo_metro", "3号線銀座線"): "#F39700",
    ("tokyo_metro", "4号線丸ノ内線"): "#E60012",
    ("tokyo_metro", "4号線丸ノ内線分岐線"): "#E60012",
    ("tokyo_metro", "5号線東西線"): "#00A7DB",
    ("tokyo_metro", "7号線南北線"): "#00ADA9",
    ("tokyo_metro", "8号線有楽町線"): "#D7C447",
    ("tokyo_metro", "9号線千代田線"): "#009944",
    ("tokyo_monorail", "東京モノレール羽田線"): "#4CC3E6",
    ("tokyu", "こどもの国線"): "#D9485F",
    ("tokyu", "世田谷線"): "#D9485F",
    ("tokyu", "大井町線"): "#D9485F",
    ("tokyu", "東急多摩川線"): "#D9485F",
    ("tokyu", "東急新横浜線"): "#D9485F",
    ("tokyu", "東横線"): "#D9485F",
    ("tokyu", "池上線"): "#D9485F",
    ("tokyu", "田園都市線"): "#D9485F",
    ("tokyu", "目黒線"): "#D9485F",
    ("tsukuba_express", "常磐新線"): "#2BB673",
    ("yurikamome", "東京臨海新交通臨海線"): "#4BBDDF",
}


def color_for_operator(operator_id: str) -> str:
    if operator_id in OPERATOR_COLORS:
        return OPERATOR_COLORS[operator_id]
    digest = hashlib.sha1(operator_id.encode("utf-8")).hexdigest()
    hue = int(digest[:6], 16) % 360 / 360
    red, green, blue = colorsys.hls_to_rgb(hue, 0.47, 0.58)
    return f"#{int(red * 255):02X}{int(green * 255):02X}{int(blue * 255):02X}"


def color_for_operator_line(operator_id: str, line_name: str) -> str:
    return LINE_COLORS_BY_OPERATOR_LINE.get((operator_id, line_name), color_for_operator(operator_id))


def color_source_for_operator_line(operator_id: str, line_name: str) -> str:
    if (operator_id, line_name) in LINE_COLORS_BY_OPERATOR_LINE:
        return "official_line"
    return "operator_fallback"
