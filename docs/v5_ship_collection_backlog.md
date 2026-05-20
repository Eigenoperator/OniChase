# OniChase V5 Ship Collection Backlog

Last updated: 2026-05-20 14:40:29 PDT

This backlog is the collection list for V5 ferry/ship gameplay. It is not a
playable dataset by itself. A route becomes playable only after the source
inventory has official ports, timetable, calendar notes, adult passenger fare,
and connector status.

## Inclusion Rule

Collect scheduled public passenger transport:

- Long-distance ferries, including overnight ferries.
- Intercity ferries and high-speed passenger boats.
- Island access ferries used as public transport.
- Urban water buses only when they work as point-to-point public transport.

Do not collect pure sightseeing cruises as gameplay transport unless they also
publish a normal scheduled transport route between usable nodes.

## Priority 1: Long-Distance And Night Ferries

These are highest value because they create large map jumps and the long/night
ferry reveal rule matters.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| source inventory | 太平洋フェリー | 名古屋・仙台・苫小牧 | 名古屋港, 仙台港, 苫小牧西港 | Multi-leg route, long/night reveal. |
| source inventory | 商船三井さんふらわあ | 大洗・苫小牧 | 大洗港, 苫小牧西港 | Hokkaido trunk. |
| source inventory | 商船三井さんふらわあ | 大阪・別府 | 大阪南港, 別府港 | Kansai-Kyushu overnight. |
| source inventory | 商船三井さんふらわあ | 神戸・大分 | 神戸港, 大分港 | Kansai-Kyushu overnight. |
| source inventory | 商船三井さんふらわあ | 大阪・志布志 | 大阪南港, 志布志港 | Kansai-southern Kyushu. |
| source inventory | 新日本海フェリー | 舞鶴・小樽 | 舞鶴港, 小樽港 | Japan Sea trunk. |
| source inventory | 新日本海フェリー | 敦賀・苫小牧東 | 敦賀港, 苫小牧東港 | Japan Sea trunk. |
| source inventory | 新日本海フェリー | 新潟・小樽 | 新潟港, 小樽港 | Calendar-sensitive. |
| source inventory | 新日本海フェリー | 新潟・秋田・苫小牧東 | 新潟港, 秋田港, 苫小牧東港 | Multi-leg route. |
| source inventory | 阪九フェリー | 泉大津・新門司 | 泉大津港, 新門司港 | Kansai-Kyushu overnight. |
| source inventory | 阪九フェリー | 神戸・新門司 | 神戸港, 新門司港 | Kansai-Kyushu overnight. |
| source inventory | 名門大洋フェリー | 大阪南港・新門司 | 大阪南港, 新門司港 | Multiple daily night sailings. |
| source inventory | 東京九州フェリー | 横須賀・新門司 | 横須賀港, 新門司港 | Long-distance trunk. |
| source inventory | オーシャン東九フェリー | 東京・徳島・新門司 | 東京港, 徳島港, 新門司港 | Multi-leg route. |
| source inventory | 宮崎カーフェリー | 神戸・宮崎 | 神戸港, 宮崎港 | Kansai-Miyazaki overnight. |
| source inventory | シルバーフェリー | 八戸・苫小牧 | 八戸港, 苫小牧西港 | Hokkaido trunk. |
| source inventory | 津軽海峡フェリー | 青森・函館 | 青森港, 函館港 | High-frequency sea link. |
| source inventory | 津軽海峡フェリー | 大間・函館 | 大間港, 函館港 | Shortest Honshu-Hokkaido ferry. |
| source inventory | 津軽海峡フェリー | 青森・室蘭 | 青森港, 室蘭港 | Current/seasonal status must be checked. |
| source inventory | 青函フェリー | 青森・函館 | 青森港, 函館港 | Parallel operator; de-duplicate by operator/trip. |

## Priority 2: Major Island And Regional Ferries

These are important because they unlock islands and alternative regional routes.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| source inventory | 佐渡汽船 | 新潟・両津 | 新潟港, 両津港 | Ferry and jetfoil need separate service classes. |
| source inventory | 佐渡汽船 | 直江津・小木 | 直江津港, 小木港 | Seasonal/calendar-sensitive. |
| source inventory | 東海汽船 | 東京・伊豆諸島 | 竹芝, 横浜, 大島, 利島, 新島, 式根島, 神津島, 三宅島, 御蔵島, 八丈島 | Multiple vessels/classes. |
| source inventory | 神新汽船 | 下田・伊豆諸島 | 下田, 利島, 新島, 式根島, 神津島 | Check current operating days. |
| source inventory | 隠岐汽船 | 本土・隠岐諸島 | 七類港, 境港, 西郷港, 別府港, 来居港, 菱浦港 | Ferry/high-speed split. |
| source inventory | ハートランドフェリー | 稚内・利尻・礼文 | 稚内港, 鴛泊港, 香深港 | Airport bus connector already exists near Wakkanai. |
| source inventory | ハートランドフェリー | 江差・奥尻 | 江差港, 奥尻港 | Airport bus connector exists for 奥尻. |
| source inventory | 羽幌沿海フェリー | 羽幌・焼尻・天売 | 羽幌港, 焼尻港, 天売港 | Island access. |
| source inventory | 九州商船 | 長崎/佐世保・五島 | 長崎港, 佐世保港, 福江港, 奈良尾港, 有川港 | Ferry/high-speed split. |
| source inventory | 五島産業汽船 | 長崎・上五島 | 長崎港, 鯛ノ浦港, 有川港 | Parallel source with overlap risk. |
| source inventory | マルエーフェリー | 鹿児島・奄美・沖縄 | 鹿児島新港, 名瀬港, 亀徳港, 和泊港, 与論港, 那覇港 | Long island chain, calendar-heavy. |
| source inventory | マリックスライン | 鹿児島・奄美・沖縄 | 鹿児島新港, 名瀬港, 亀徳港, 和泊港, 与論港, 那覇港 | Parallel operator, de-duplicate by sailing. |
| source inventory | 鹿児島商船 | 鹿児島・種子島・屋久島 | 鹿児島港, 西之表港, 宮之浦港, 安房港 | High-speed and ferry variants. |
| source inventory | 折田汽船 | 鹿児島・屋久島 | 鹿児島港, 宮之浦港 | Ferry Yakushima route. |
| source inventory | 三島村 | 鹿児島・三島 | 鹿児島港, 竹島港, 硫黄島港, 黒島港 | Low-frequency public route. |
| source inventory | 十島村 | 鹿児島・トカラ列島 | 鹿児島港, 口之島, 中之島, 平島, 諏訪之瀬島, 悪石島, 小宝島, 宝島 | Low-frequency public route. |
| source inventory | 久米商船 | 那覇・渡名喜・久米島 | 那覇泊港, 渡名喜港, 兼城港 | Okinawa island access. |
| source inventory | 座間味村 | 那覇・座間味/阿嘉 | 那覇泊港, 座間味港, 阿嘉港 | Ferry/high-speed split. |
| source inventory | 渡嘉敷村 | 那覇・渡嘉敷 | 那覇泊港, 渡嘉敷港 | Ferry/high-speed split. |
| source inventory | 粟国村 | 那覇・粟国 | 那覇泊港, 粟国港 | Low-frequency island access. |
| source inventory | 安栄観光 | 石垣・八重山諸島 | 石垣港, 竹富港, 小浜港, 黒島港, 西表大原港, 西表上原港, 波照間港, 鳩間港 | High-frequency island network. |
| source inventory | 八重山観光フェリー | 石垣・八重山諸島 | 石垣港, 竹富港, 小浜港, 黒島港, 西表大原港, 西表上原港, 波照間港, 鳩間港 | Parallel operator, overlap risk. |

## Priority 3: Setouchi, Kyushu, And Short Intercity Ferries

These fill missing sea crossings where rail/bus detours are large.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| source inventory | 南海フェリー | 和歌山・徳島 | 和歌山港, 徳島港 | Direct rail connector at 和歌山港. |
| source inventory | ジャンボフェリー | 神戸・小豆島・高松 | 神戸港, 坂手港, 高松東港 | High gameplay value around Shikoku/Kansai. |
| source inventory | 小豆島フェリー/四国フェリー | 高松・土庄 | 高松港, 土庄港 | High-frequency island access. |
| source inventory | 国際両備フェリー | 高松・池田 | 高松港, 池田港 | Check overlap with 小豆島 routes. |
| source inventory | 小豆島豊島フェリー | 土庄・豊島・宇野 | 土庄港, 唐櫃港, 家浦港, 宇野港 | Island connector. |
| source inventory | 瀬戸内海汽船/石崎汽船 | 広島/呉・松山 | 広島港, 呉港, 松山観光港 | Ferry and superjet split. |
| source inventory | 防予フェリー | 柳井・三津浜 | 柳井港, 三津浜港 | Yamaguchi-Ehime link. |
| source inventory | 国道九四フェリー | 佐賀関・三崎 | 佐賀関港, 三崎港 | Kyushu-Shikoku shortest link. |
| source inventory | 宇和島運輸フェリー | 八幡浜・別府/臼杵 | 八幡浜港, 別府港, 臼杵港 | Competes with 九四オレンジ. |
| source inventory | 九四オレンジフェリー | 八幡浜・臼杵 | 八幡浜港, 臼杵港 | Overlap risk with 宇和島運輸. |
| source inventory | 熊本フェリー | 熊本・島原 | 熊本港, 島原港 | Fast Kyushu crossing. |
| source inventory | 九商フェリー | 熊本・島原 | 熊本港, 島原港 | Parallel operator, overlap risk. |
| source inventory | 島鉄フェリー | 口之津・鬼池 | 口之津港, 鬼池港 | Amakusa-Shimabara link. |
| source inventory | JR西日本宮島フェリー | 宮島口・宮島 | 宮島口, 宮島 | Railway-adjacent short route. |
| source inventory | 宮島松大汽船 | 宮島口・宮島 | 宮島口, 宮島 | Parallel operator. |
| source inventory | 東京湾フェリー | 久里浜・金谷 | 久里浜港, 金谷港 | Tokyo Bay shortcut. |

## Priority 4: Urban Water Transport Candidates

These are lower priority. They should stay non-playable until we confirm they
are useful transport rather than only sightseeing.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| review | 東京都観光汽船/Tokyo Cruise | 隅田川・東京湾 | 浅草, 日の出, 浜離宮, お台場海浜公園, 豊洲 | Mostly sightseeing; verify transport usefulness. |
| review | 大阪水上バス | 大阪市内 | 淀屋橋, 大阪城港, 八軒家浜 ほか | Likely sightseeing; low priority. |
| review | 琵琶湖汽船 | 大津・竹生島 ほか | 大津港, 竹生島港 ほか | Mostly tourism; only collect if useful as transport. |

## Collection Stages

Each row advances through:

1. `source inventory`: official URLs and scope recorded.
2. `ports`: port coordinates and node names normalized.
3. `timetable`: directional departures and arrivals collected.
4. `calendar`: operating-day rules collected.
5. `fare`: adult passenger fare collected.
6. `connectors`: rail/bus/walk access is known.
7. `playable`: route is included in `docs/data/v5_ship_map.geojson`.

## Current Red Lines

- Do not invent port connectors. If a port lacks rail access, wait for real bus
  connector data or walking access.
- Do not merge parallel operators unless the official trips are the same
  sailing; duplicate detection must use operator, route, departure, arrival,
  and vessel/service identity.
- Long-distance/night ferry boarding should reveal; short local/island routes
  should not reveal by default.
- Unknown fare blocks playable promotion.
