# OniChase V5 Ship Collection Backlog

Last updated: 2026-05-20 14:40:29 PDT

This backlog is the collection list for V5 ferry/ship gameplay. It is anchored
to the MLIT scheduled passenger-ship operator list and the Japan Long Course
Ferry Service Association route list, then ordered by gameplay value. It is not
a playable dataset by itself. A route becomes playable only after the source
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

## Validation Sources

- MLIT `旅客船・フェリー事業者の運航情報` is the master discovery source for
  scheduled passenger/ferry operators that publish web timetables.
- 日本長距離フェリー協会 is the cross-check source for the 15 long-distance
  ferry route groups.
- Regional associations such as 四国旅客船協会 are used to catch important
  intercity gaps that are not obvious from operator names alone.
- Operator official pages remain the source of truth for timetable, fare, and
  service-calendar extraction.

Current confidence:

- Priority 1 long-distance/night ferry list is complete against the Japan Long
  Course Ferry Service Association, with one correction: 新日本海フェリー's
  Japan Sea multi-leg route must keep 敦賀 in the group.
- Priority 2 and 3 are now a validated collection wave, not a complete national
  closure. The MLIT long tail contains many local island ferries; they are kept
  in the discovery backlog and promoted by gameplay value and connector
  readiness.
- `data/v5_ship_mlit_discovery.json` snapshots the full MLIT web-source
  discovery baseline. It currently contains 199 scheduled operator-route
  entries: 150 public candidates, 43 municipal scheduled candidates, and 6
  review-required sightseeing/water-bus candidates.

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
| source inventory | 新日本海フェリー | 敦賀・新潟・秋田・苫小牧東 | 敦賀港, 新潟港, 秋田港, 苫小牧東港 | Multi-leg route. |
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
| source inventory | 四国開発フェリー | 東予/新居浜・神戸/大阪 | 東予港, 新居浜港, 神戸港, 大阪南港 | Missing from first draft; required by 四国旅客船協会 cross-check. |
| source inventory | 松山・小倉フェリー | 松山・小倉 | 松山観光港, 小倉港 | Missing from first draft; overnight Setouchi-Kyushu route. |

## Priority 2: Major Island And Regional Ferries

These are important because they unlock islands and alternative regional routes.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| source inventory | 佐渡汽船 | 新潟・両津 | 新潟港, 両津港 | Ferry and jetfoil need separate service classes. |
| source inventory | 佐渡汽船 | 直江津・小木 | 直江津港, 小木港 | Seasonal/calendar-sensitive. |
| source inventory | 東海汽船 | 東京・伊豆諸島 | 竹芝, 横浜, 大島, 利島, 新島, 式根島, 神津島, 三宅島, 御蔵島, 八丈島 | Multiple vessels/classes. |
| source inventory | 神新汽船 | 下田・伊豆諸島 | 下田, 利島, 新島, 式根島, 神津島 | Check current operating days. |
| source inventory | 小笠原海運 | 東京・父島 | 竹芝, 父島二見港 | Critical remote-island route; long voyage, reveal. |
| source inventory | 伊豆諸島開発 | 八丈島・青ヶ島 / 父島・母島 | 八丈島, 青ヶ島, 父島, 母島 | Connects islands not reachable by rail/air alone. |
| source inventory | 隠岐汽船 | 本土・隠岐諸島 | 七類港, 境港, 西郷港, 別府港, 来居港, 菱浦港 | Ferry/high-speed split. |
| source inventory | ハートランドフェリー | 稚内・利尻・礼文 | 稚内港, 鴛泊港, 香深港 | Airport bus connector already exists near Wakkanai. |
| source inventory | ハートランドフェリー | 江差・奥尻 | 江差港, 奥尻港 | Airport bus connector exists for 奥尻. |
| source inventory | 羽幌沿海フェリー | 羽幌・焼尻・天売 | 羽幌港, 焼尻港, 天売港 | Island access. |
| source inventory | 九州商船 | 長崎/佐世保・五島 | 長崎港, 佐世保港, 福江港, 奈良尾港, 有川港 | Ferry/high-speed split. |
| source inventory | 五島産業汽船 | 長崎・上五島 | 長崎港, 鯛ノ浦港, 有川港 | Parallel source with overlap risk. |
| source inventory | 九州郵船 | 博多・壱岐・対馬 | 博多港, 郷ノ浦港, 芦辺港, 厳原港, 比田勝港, 印通寺港, 唐津東港 | Major Kyushu island trunk. |
| source inventory | マルエーフェリー | 鹿児島・奄美・沖縄 | 鹿児島新港, 名瀬港, 亀徳港, 和泊港, 与論港, 那覇港 | Long island chain, calendar-heavy. |
| source inventory | マリックスライン | 鹿児島・奄美・沖縄 | 鹿児島新港, 名瀬港, 亀徳港, 和泊港, 与論港, 那覇港 | Parallel operator, de-duplicate by sailing. |
| source inventory | 奄美海運 | 鹿児島・喜界・奄美群島 | 鹿児島新港, 喜界港, 名瀬港, 古仁屋港, 平土野港, 知名港 | Missing from first draft; separate island-chain operator. |
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
| source inventory | 周防大島松山フェリー | 柳井・伊保田・松山 | 柳井港, 伊保田港, 三津浜港 | Parallel/branch route; check overlap with 防予. |
| source inventory | 周防灘フェリー | 徳山・竹田津 | 徳山港, 竹田津港 | Yamaguchi-Oita shortcut. |
| source inventory | 国道九四フェリー | 佐賀関・三崎 | 佐賀関港, 三崎港 | Kyushu-Shikoku shortest link. |
| source inventory | 宇和島運輸フェリー | 八幡浜・別府/臼杵 | 八幡浜港, 別府港, 臼杵港 | Competes with 九四オレンジ. |
| source inventory | 九四オレンジフェリー | 八幡浜・臼杵 | 八幡浜港, 臼杵港 | Overlap risk with 宇和島運輸. |
| source inventory | 熊本フェリー | 熊本・島原 | 熊本港, 島原港 | Fast Kyushu crossing. |
| source inventory | 九商フェリー | 熊本・島原 | 熊本港, 島原港 | Parallel operator, overlap risk. |
| source inventory | 島鉄フェリー | 口之津・鬼池 | 口之津港, 鬼池港 | Amakusa-Shimabara link. |
| source inventory | JR西日本宮島フェリー | 宮島口・宮島 | 宮島口, 宮島 | Railway-adjacent short route. |
| source inventory | 宮島松大汽船 | 宮島口・宮島 | 宮島口, 宮島 | Parallel operator. |
| source inventory | 東京湾フェリー | 久里浜・金谷 | 久里浜港, 金谷港 | Tokyo Bay shortcut. |
| source inventory | ふじさん駿河湾フェリー | 清水・土肥 | 清水港, 土肥港 | Suruga Bay shortcut. |
| source inventory | 伊勢湾フェリー | 鳥羽・伊良湖 | 鳥羽港, 伊良湖港 | Kintetsu/Meitetsu-side regional shortcut. |
| source inventory | 津エアポートライン | 津新港・中部国際空港 | 津新港, 空港島 | Airport-access ship; later must integrate with flight nodes. |
| source inventory | 神戸-関空ベイ・シャトル | 神戸空港・関西空港 | 神戸空港海上アクセスターミナル, 関西空港 | Airport-to-airport ship; high V5 multimodal value. |
| source inventory | 淡路ジェノバライン | 明石・岩屋 | 明石港, 岩屋港 | Short urban/regional public transport. |
| source inventory | 四国汽船 | 高松/宇野・直島 | 高松港, 宇野港, 宮浦港, 本村港 | Naoshima public island access. |
| source inventory | 桜島フェリー | 鹿児島・桜島 | 鹿児島港, 桜島港 | High-frequency public ferry. |
| source inventory | 垂水フェリー | 鴨池・垂水 | 鴨池港, 垂水港 | Kagoshima Bay shortcut. |
| source inventory | 有明フェリー | 多比良・長洲 | 多比良港, 長洲港 | Ariake Sea shortcut. |
| source inventory | 三和フェリー | 蔵之元・牛深 | 蔵之元港, 牛深港 | Amakusa-Kagoshima link. |

## Priority 4: Urban Water Transport Candidates

These are lower priority. They should stay non-playable until we confirm they
are useful transport rather than only sightseeing.

| Status | Operator | Route Group | Ports To Collect | Notes |
| --- | --- | --- | --- | --- |
| review | 東京都観光汽船/Tokyo Cruise | 隅田川・東京湾 | 浅草, 日の出, 浜離宮, お台場海浜公園, 豊洲 | Mostly sightseeing; verify transport usefulness. |
| review | 大阪水上バス | 大阪市内 | 淀屋橋, 大阪城港, 八軒家浜 ほか | Likely sightseeing; low priority. |
| review | 琵琶湖汽船 | 大津・竹生島 ほか | 大津港, 竹生島港 ほか | Mostly tourism; only collect if useful as transport. |

## MLIT Long-Tail Discovery Backlog

The MLIT scheduled-operator page lists many local island routes beyond the
first playable collection wave. They are now stored in:

- `data/v5_ship_mlit_discovery.json`
- generator: `scripts/ingest/collect_v5_ship_mlit_discovery.py`

They should not be ignored, but they should be promoted after the high-value
trunk routes because each one needs connectors and overlap checks.

Known long-tail groups to keep in discovery:

- 東北: 塩竈-浦戸諸島, 酒田-飛島, 石巻-田代島-網地島, 女川-江島.
- 北陸信越: 粟島, 舳倉島.
- 中部: 鳥羽-神島, 熱海-初島, 一色-佐久島, 名鉄海上観光船 routes.
- 近畿/兵庫: 大阪市渡船, 丹後湾内, 沼島, 家島, 坊勢.
- 中国/瀬戸内: 広島-切串/似島/江田島方面, 竹原-大崎上島,
  尾道/因島/弓削, 笠岡諸島, 萩-見島, 大津島, 平郡, 野島.
- 四国: 男木/女木, 豊島, 本島, 粟島, 佐柳, 伊吹, 出羽島, 伊島,
  中島, 興居島, 青島, 今治-島しょ部.
- 九州: 相島, 大入島, 姫島, 唐津諸島, 平戸/黒島/五島周辺,
  甑島, 屋久島町内, 御所浦, 島浦, 福岡市営航路, 北九州市営航路.
- 沖縄: 伊江, 伊平屋, 伊是名, 津堅, 与那国, 多良間, 大神, 久高,
  船浮, 大東, 水納.

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
