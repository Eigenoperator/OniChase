# OniChase V5 Bus Collection Backlog

Generated from the current V5 bus audits on `2026-05-19`.

## Current Playable Source Layer

- GTFS / official runtime bundle: 454 successfully parsed GTFS feeds plus promoted official bus sources.
- Bus stops: 89,238.
- Bus routes: 5,255.
- Bus trips: 79,244.
- Stop times: 2,270,528.
- Runtime planner tiles: 422 tiles.
- Saturday active trips in planner tiles: 28,161.
- Walking connectors: 111,737.
- Routes with fare-rule coverage: 4,553.

## Highest Priority Gap

Airport access is the most important missing data family because V5 flight
gameplay depends on reliable airport ground access.

Current airport access audit:

- 43 airports covered by GTFS/official airport-class bus routes.
- 2 airports have nearby GTFS bus stops but no airport-class route.
- 4 airports have GTFS bus stops only within the wider 5 km review radius.
- 27 airports still have no bus stop within 5 km in this source layer.

## First Airport-Bus Parser Targets

These airports have high flight volume and no GTFS bus stop coverage in the
current audit. They should be collected from official airport/operator pages
before lower-volume airports.

| Priority | Airport | Current status | Initial official source target |
| --- | --- | --- | --- |
| 1 | HND | no GTFS stop within 5 km | Haneda Airport express/route bus access page |
| 2 | CTS | no GTFS stop within 5 km | New Chitose Airport bus page; Hokkaido Chuo Bus airport liner |
| 3 | ITM | no GTFS stop within 5 km | Osaka Itami Airport bus page; Hankyu Kanko Bus/Hanshin/Kintetsu links |
| 4 | KIX | no GTFS stop within 5 km | Kansai Airport bus page; Kansai Airport Transportation Enterprise |
| 5 | KOJ | no GTFS stop within 5 km | Kagoshima Airport access bus operators |
| 6 | KMI | no GTFS stop within 5 km | Miyazaki Airport access bus operators |
| 7 | UKB | no GTFS stop within 5 km | Kobe Airport access bus operators |
| 8 | ISG | no GTFS stop within 5 km | Ishigaki Airport bus operators |
| 9 | NGS | no GTFS stop within 5 km | Nagasaki Airport access bus operators |
| 10 | KIJ | official direct bus playable | Niigata Airport access bus operators |

## Collection Progress

### 2026-05-16

Completed first official-source collection pass:

- KIX / KATE official timetable pages.
  - Script: `scripts/ingest/collect_v5_kate_airport_bus.py`
  - Source output: `data/v5_kate_official_airport_bus_source.json`
  - Docs copy: `docs/data/v5_kate_official_airport_bus_source.json`
  - Audit: `data/v5_kate_official_airport_bus_audit.json`
  - Result: 26 official KATE route pages collected; 17 have active timetable
    rows; 731 official bus trips extracted.
- Priority airport official source index for HND / CTS / ITM / KIX.
  - Script: `scripts/ingest/collect_v5_airport_bus_source_index.py`
  - Source output: `data/v5_airport_bus_official_source_index.json`
  - Docs copy: `docs/data/v5_airport_bus_official_source_index.json`
  - Result: 380 official/source links indexed; 110 route/timetable candidates.

Current next parser order:

1. HND: collect Airport Transport Service / Limousine Bus pages. The site is
   more protected than Keikyu and may require a browser-backed collector or
   official PDF fallback.
2. CTS: add Hokuto Kotsu after the Hokkaido Chuo Bus parser.
3. ITM: promote the linked-page source pass into operator-specific parsers for
   Hankyu Kanko Bus, Hankyu Bus, Itami City Bus, and the long-distance
   operators.
4. KIX: convert collected KATE source data into normalized bus bundle rows and
   run duplicate checks against the existing GTFS layer.
5. Next airports: KOJ, KMI, UKB, ISG, NGS, KIJ.

Completed second official-source collection pass:

- HND / Keikyu Bus official airport timetable fragments.
  - Script: `scripts/ingest/collect_v5_keikyu_haneda_bus.py`
  - Source output: `data/v5_keikyu_haneda_official_bus_source.json`
  - Docs copy: `docs/data/v5_keikyu_haneda_official_bus_source.json`
  - Audit: `data/v5_keikyu_haneda_official_bus_audit.json`
  - Result: 56 Haneda route entries collected; 53 have parseable timetable
    rows; 1,852 official bus trips extracted.
- CTS / Hokkaido Chuo Bus official New Chitose Airport timetable pages.
  - Script: `scripts/ingest/collect_v5_chuo_cts_bus.py`
  - Source output: `data/v5_chuo_cts_official_bus_source.json`
  - Docs copy: `docs/data/v5_chuo_cts_official_bus_source.json`
  - Audit: `data/v5_chuo_cts_official_bus_audit.json`
  - Result: 14 official route-direction pages collected; all 14 parse; 281
    official bus trips extracted.
- ITM / Osaka Itami official airport bus linked pages.
  - Script: `scripts/ingest/collect_v5_itm_airport_bus_pages.py`
  - Source output: `data/v5_itm_official_bus_pages.json`
  - Docs copy: `docs/data/v5_itm_official_bus_pages.json`
  - Audit: `data/v5_itm_official_bus_pages_audit.json`
  - Result: 35 linked operator/source pages collected or attempted; 23 pages
    contain parseable timetable time text and should be promoted to dedicated
    operator parsers.

Completed third official-source collection pass:

- CTS / Hokuto Kotsu official New Chitose Airport timetable pages.
  - Script: `scripts/ingest/collect_v5_hokuto_cts_bus.py`
  - Source output: `data/v5_hokuto_cts_official_bus_source.json`
  - Docs copy: `docs/data/v5_hokuto_cts_official_bus_source.json`
  - Audit: `data/v5_hokuto_cts_official_bus_audit.json`
  - Result: 8 official route pages collected; 7 have parseable timetable rows;
    319 official bus trips extracted.
- Official-source overlap audit against the current GTFS bus bundle.
  - Script: `scripts/ingest/audit_v5_official_bus_source_overlap.py`
  - Audit: `data/v5_official_bus_source_overlap_audit.json`
  - Result: 104 official routes checked; 3,183 official trips represented in
    source files; 91 routes have no likely GTFS overlap; 13 routes have no
    active official trips. No duplicate GTFS overlap candidates were found by
    the current name/operator heuristic.
- Next airport page source pass for KOJ / KMI / UKB / ISG.
  - Script: `scripts/ingest/collect_v5_next_airport_bus_pages.py`
  - Source output: `data/v5_next_airport_bus_pages.json`
  - Docs copy: `docs/data/v5_next_airport_bus_pages.json`
  - Audit: `data/v5_next_airport_bus_pages_audit.json`
  - Result: 10 airport/operator pages cached; 4 pages contain parseable
    timetable time text. KMI can likely become the next full parser; KOJ and
    UKB need operator-specific parsing; ISG pages appear partly image/embedded
    and need a separate handling path.

Completed fourth official-source collection pass:

- KMI / Miyazaki Airport official summary timetable.
  - Script: `scripts/ingest/collect_v5_miyazaki_airport_bus.py`
  - Source output: `data/v5_miyazaki_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_miyazaki_airport_official_bus_source.json`
  - Audit: `data/v5_miyazaki_airport_official_bus_audit.json`
  - Result: 4 airport-bus route summaries parsed; 125 real departure times
    extracted.
  - Limitation: the official airport page publishes summary departure times but
    not complete arrival times or intermediate stop sequences. Do not promote
    this source to full playable bus trips until an operator stop-order source
    is found, or mark it explicitly as departure-summary-only.
- KOJ / Kagoshima Kotsu official airport-bus PDFs.
  - Script: `scripts/ingest/collect_v5_kagoshima_airport_bus_pdfs.py`
  - Source output: `data/v5_kagoshima_airport_official_bus_pdfs.json`
  - Docs copy: `docs/data/v5_kagoshima_airport_official_bus_pdfs.json`
  - Audit: `data/v5_kagoshima_airport_official_bus_pdfs_audit.json`
  - Result: 8 official PDFs cached; all 8 contain extractable timetable text.
    Next step is a PDF table parser for actual route/stop/trip normalization.

Completed fifth official-source collection pass:

- KOJ / Kagoshima Airport conservative PDF table parser.
  - Script: `scripts/ingest/parse_v5_kagoshima_airport_bus_pdf_tables.py`
  - Source output: `data/v5_kagoshima_airport_official_bus_tables.json`
  - Docs copy: `docs/data/v5_kagoshima_airport_official_bus_tables.json`
  - Audit: `data/v5_kagoshima_airport_official_bus_tables_audit.json`
  - Result: 4 PDFs parsed into reliable route tables; 4 routes and 33 complete
    official trips extracted.
  - Kept as PDF source only for now: Kagoshima city 10-minute interval table,
    Ibusuki/Taniyama, Kirishima, and Myoken route bus. These need a more
    specialized multi-page / dense-table parser.
- UKB / Nishinihon JR Bus Kobe Airport highway bus.
  - Script: `scripts/ingest/collect_v5_ukb_nishinihonjr_bus.py`
  - Source output: `data/v5_ukb_nishinihonjr_official_bus_source.json`
  - Docs copy: `docs/data/v5_ukb_nishinihonjr_official_bus_source.json`
  - Audit: `data/v5_ukb_nishinihonjr_official_bus_audit.json`
  - Result: 2 official direction pages parsed; 26 trips serving Kobe Airport
    extracted for the Kobe Airport ⇔ Tokushima route.
- Official-source overlap audit expanded to include KMI, KOJ parsed tables, and
  UKB Nishinihon JR Bus.
  - Result: 113 official routes checked; 3,334 official trips represented in
    source files; no likely GTFS duplicate overlap found by the current
    heuristic.

Completed sixth official-source collection pass:

- NGS / Nagasaki Airport official monthly HTML timetables.
  - Script: `scripts/ingest/collect_v5_nagasaki_airport_bus.py`
  - Source output: `data/v5_nagasaki_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_nagasaki_airport_official_bus_source.json`
  - Audit: `data/v5_nagasaki_airport_official_bus_audit.json`
  - Result: 4 route-direction tables parsed; 112 official trips extracted.
  - Note: the current source pages are monthly validity pages, so this parser
    should be refreshed for each release service month.
- KIJ / Niigata Airport official Niigata Kotsu PDF sources.
  - Script: `scripts/ingest/collect_v5_niigata_airport_bus_pdfs.py`
  - Source output: `data/v5_niigata_airport_official_bus_pdfs.json`
  - Docs copy: `docs/data/v5_niigata_airport_official_bus_pdfs.json`
  - Audit: `data/v5_niigata_airport_official_bus_pdfs_audit.json`
  - Result: 2 official PDFs cached. The first pass recorded them as
    image/vector-like because `pdftotext` did not expose `HH:MM` tokens, but
    the visible official rows were later normalized into a playable direct
    新潟駅 ⇔ 新潟空港 airport-bus source.
- Official-source overlap audit expanded to include NGS.
  - Result: 117 official routes checked; 3,446 official trips represented in
    source files; no likely GTFS duplicate overlap found by the current
    heuristic.

Completed seventh official-source collection pass:

- ISG / Ishigaki Airport official Karry Kanko direct bus timetable.
  - Script: `scripts/ingest/collect_v5_ishigaki_airport_bus.py`
  - Source output: `data/v5_ishigaki_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_ishigaki_airport_official_bus_source.json`
  - Audit: `data/v5_ishigaki_airport_official_bus_audit.json`
  - Result: 1 official direct-bus route normalized; 40 official trips extracted
    for 石垣空港 ⇔ 石垣港離島ターミナル. Adult fare is recorded as ¥550.
- ISG / Azuma Bus official timetable PDFs.
  - The same script caches the Ishigaki Airport access page, Azuma Bus index
    page, and 10 official Azuma Bus PDF sources relevant to airport / timetable
    collection. Six PDFs expose extractable timetable text through
    `pdftotext`; four need OCR or a more specialized PDF/image path.
  - Current limitation: Azuma route ④/⑩ and wider island routes are source
    captured but not yet normalized into playable stop-time tables.
  - Official-source overlap audit expanded to include ISG Karry Kanko.
  - Result: 118 official routes checked; 3,486 official trips represented in
    source files; no likely GTFS duplicate overlap found by the current
    heuristic.

### 2026-05-19

Continued high-flight-volume airport access gap collection:

- AOJ / Aomori Airport official JR Bus Tohoku PDF timetable.
  - Script: `scripts/ingest/collect_v5_aomori_airport_bus.py`
  - Source output: `data/v5_aomori_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_aomori_airport_official_bus_source.json`
  - Audit: `data/v5_aomori_airport_official_bus_audit.json`
  - Result: 1 official route normalized; 33 endpoint-playable trips extracted
    for 青森駅 ⇔ 青森空港. Adult fare is recorded as ¥690.
  - Timetable scope: official JR Bus Tohoku PDF effective 2026-03-01; most
    trips are daily, with one airport-bound and one city-bound Tue/Thu/Sat
    service preserved at trip level.
  - Overlap audit: no GTFS duplicate found, so the route was promoted into the
    runtime bus bundle and planner tiles.

Remaining no-stop-within-5km airport gaps by current flight volume now begin:

1. ASJ / Amami Airport: 36 flights.
2. IZO / Izumo Enmusubi Airport: 34 flights.
3. IWK / Iwakuni Kintaikyo Airport: 24 flights.
4. OKJ / Okayama Momotaro Airport: 24 flights.
5. KUH / Kushiro Airport: 22 flights.
6. MMB / Memanbetsu Airport: 22 flights.
7. AKJ / Asahikawa Airport: 20 flights.
8. YGJ / Yonago Kitaro Airport: 19 flights.
9. TSJ / Tsushima Airport: 18 flights.
10. FUJ / Fukue Airport: 16 flights.

- UBJ / Yamaguchi Ube Airport official airport access bus HTML timetables.
  - Script: `scripts/ingest/collect_v5_yamaguchi_ube_airport_bus.py`
  - Source output: `data/v5_yamaguchi_ube_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_yamaguchi_ube_airport_official_bus_source.json`
  - Audit: `data/v5_yamaguchi_ube_airport_official_bus_audit.json`
  - Result: 2 official route pages normalized; 36 endpoint-playable trips
    extracted for 新山口駅 ⇔ 山口宇部空港 and 宇部新川駅 ⇔ 山口宇部空港.
  - Timetable scope: official airport site current section, effective
    2026-04-01 through 2026-05-31. This matches the current V5 bus planner
    service date.
  - Fares: 新山口駅 line ¥910; 宇部新川駅 line ¥310.
  - Overlap audit: no GTFS duplicate found for either route, so both routes
    were promoted into the runtime bus bundle and planner tiles.

- HSG / Kyushu Saga International Airport official Saga City Bus timetable.
  - Script: `scripts/ingest/collect_v5_saga_airport_bus.py`
  - Source output: `data/v5_saga_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_saga_airport_official_bus_source.json`
  - Audit: `data/v5_saga_airport_official_bus_audit.json`
  - Result: 1 official route normalized; 17 endpoint-playable trips extracted
    for 佐賀駅バスセンター ⇔ 佐賀空港.
  - Timetable scope: official Saga City Bus airport-connection timetable,
    effective 2026-03-29 through 2026-05-31.
  - Calendar scope: daily, weekday-only trial rows, and international route
    weekday-pattern rows are preserved at trip level.
  - Fare: endpoint fare ¥600.
  - Overlap audit: no GTFS duplicate found, so the route was promoted into the
    runtime bus bundle and planner tiles.

- IBR / Ibaraki Airport official access bus timetables.
  - Script: `scripts/ingest/collect_v5_ibaraki_airport_bus.py`
  - Source output: `data/v5_ibaraki_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_ibaraki_airport_official_bus_source.json`
  - Audit: `data/v5_ibaraki_airport_official_bus_audit.json`
  - Result: 3 official route families normalized; 75 endpoint-playable trips
    extracted for 水戸駅高速線, 水戸駅一般道線, and 石岡駅線.
  - Timetable scope: Mito highway/current timetable effective 2026-03-29 or
    2026-04-01 through 2026-10-24 depending on route family; Ishioka service
    effective 2026-05-01 through 2026-10-24.
  - Fares: 水戸高速線 ¥1500; 水戸一般道線 ¥1190; 石岡線 ¥680.
  - Calendar scope: daily, weekday-only, and Saturday/Sunday/holiday-only rows
    are preserved at trip level.
  - Overlap audit: no GTFS duplicate found for all 3 route families, so they
    were promoted into the runtime bus bundle and planner tiles.

### 2026-05-18

Completed eighth official-source runtime promotion pass:

- Promoted the remaining reliable KOJ / Kagoshima Kotsu airport-bus PDF tables
  into playable V5 bus routes.
  - Script: `scripts/ingest/augment_v5_bus_bundle_with_official_sources.py`
  - Added route-scoped/manual stop coordinates from NAVITIME route stop data
    and Busmap structured stop data for 国分, 垂水, 志布志, and 鹿屋 airport
    bus corridors.
  - Result: 4 official KOJ routes, 33 bus trips, 537 stopTimes, and 68 stops
    promoted into the runtime bundle.
- Also resolved the previous HND coordinate blockers for 勝沼/甲府 and 君津
  routes using scoped/manual stop coordinates.
- Rebuilt the V5 bus map and planner tiles after promotion.
  - Current total bus bundle: 5,225 routes, 78,269 trips, 89,105 stops.
  - Current playable official-source coverage: 111 routes, 3,733 trips, 892
    official stops.
  - Current map audit: 97,800 features, 448 map tiles.
  - Current planner audit: 27,295 Saturday active trips, 705,811 indexed
    stopTimes, 111,469 walking connectors, 403 planner tiles.

Remaining official-source runtime blockers:

- 1 Takamatsu Shikoku Chuo / Seisan route remains intentionally blocked
  because the existing GTFS layer already contains the same 西讃観光
  高松空港 ⇔ 観音寺・四国中央 airport route with a valid 2026-03-29 to
  2027-03-31 service window. Do not append the official PDF as a duplicate;
  replace/suppress the GTFS route only if we explicitly choose source
  precedence later.
- 20 official source routes are empty/no-trip/cancelled and are not playable
  candidates yet.

Completed ninth official-source runtime promotion pass:

- KMI / Miyazaki Kotsu official route PDF parser.
  - Script: `scripts/ingest/collect_v5_miyazaki_airport_bus.py`
  - Source output: `data/v5_miyazaki_airport_official_bus_source.json`
  - Docs copy: `docs/data/v5_miyazaki_airport_official_bus_source.json`
  - Audit: `data/v5_miyazaki_airport_official_bus_audit.json`
  - Result: replaced the previous airport-page summary-only source with
    Miyazaki Kotsu official PDF timetable rows for 宮崎駅, 西都城,
    飫肥・日南, and シーガイア airport corridors.
  - Playable output: 4 KMI routes, 147 trips, and 344 stopTimes promoted into
    runtime. The シーガイア service is marked weekend-only instead of daily.
- Official-source augmenter support:
  - `serviceDays` is now respected when building calendar rows, so official
    sources can emit weekday/weekend-only bus services without being flattened
    to daily service.
- Rebuilt the V5 bus map and planner tiles after KMI promotion.
  - Current total bus bundle: 5,229 routes, 78,416 trips, 89,114 stops.
  - Current map audit: 97,812 features, 450 map tiles.
  - Current planner audit: 27,404 Saturday active trips, 706,039 indexed
    stopTimes, 111,490 walking connectors, 405 planner tiles.

Completed tenth official-source runtime promotion pass:

- KIJ / Niigata Kotsu official airport PDF parser upgrade.
  - Script: `scripts/ingest/collect_v5_niigata_airport_bus_pdfs.py`
  - Source output: `data/v5_niigata_airport_official_bus_pdfs.json`
  - Docs copy: `docs/data/v5_niigata_airport_official_bus_pdfs.json`
  - Audit: `data/v5_niigata_airport_official_bus_pdfs_audit.json`
  - Result: promoted the official 新潟駅 ⇔ 新潟空港 direct limousine bus
    endpoint timetable into runtime. Later promoted the official
    新潟空港 → 新潟駅 各停 万代シテイ経由 airport departures as endpoint-playable
    trips with weekday/weekend calendars.
  - Playable output after the remaining-source pass: 2 KIJ routes, 89 trips,
    178 stopTimes, and ¥470 adult fare.
  - Safety note: 万代シテイ経由 local buses are endpoint-playable only. The
    official PDF gives airport departures and an about-35-minute runtime, but
    it does not expose complete intermediate stop-times.
- Airport stop matching was tightened so a city station name like 新潟駅
  cannot be reverse-matched to 新潟空港 just because the normalized station
  name is a substring of the airport name.
- Rebuilt the V5 bus map and planner tiles after KIJ promotion.
  - Current total bus bundle: 5,230 routes, 78,465 trips, 89,116 stops.
  - Current map audit: 97,815 features, 450 map tiles.
  - Current planner audit: 27,453 Saturday active trips, 706,137 indexed
    stopTimes, 111,493 walking connectors, 405 planner tiles.

Completed eighth official-source collection pass:

- ITM / Hankyu Kanko Bus official Osaka Itami Airport limousine timetables.
  - Script: `scripts/ingest/collect_v5_itm_hankyu_kanko_bus.py`
  - Source output: `data/v5_itm_hankyu_kanko_official_bus_source.json`
  - Docs copy: `docs/data/v5_itm_hankyu_kanko_official_bus_source.json`
  - Audit: `data/v5_itm_hankyu_kanko_official_bus_audit.json`
  - Result: 13 official route pages parsed; all 13 have active timetable rows;
    602 official bus trips extracted. Parsed routes include the main Itami
    airport limousine corridors toward Shin-Osaka, Osaka/Umeda, Namba,
    Tennoji/Abenobashi, Uehommachi, Nara, Kyoto, Himeji, Kobe Sannomiya,
    Koshien, USJ, and KIX.
- Official-source overlap audit expanded to include ITM Hankyu Kanko Bus.
  - Result: 131 official routes checked; 4,088 official trips represented in
    source files; no likely GTFS duplicate overlap found by the current
    heuristic.

Completed ninth official-source collection pass:

- TAK / Takamatsu Airport official airport-bus source capture.
  - Script: `scripts/ingest/collect_v5_takamatsu_airport_bus_sources.py`
  - Source output: `data/v5_takamatsu_airport_official_bus_sources.json`
  - Docs copy: `docs/data/v5_takamatsu_airport_official_bus_sources.json`
  - Audit: `data/v5_takamatsu_airport_official_bus_sources_audit.json`
  - Result: 10 route/fare summary sections captured from the official airport
    access page and 17 explicit bus/timetable/fare/operator links cached or
    classified. Two official PDFs expose extractable timetable text and six
    linked HTML pages contain time text.
  - Limitation: this is source capture only. Takamatsu city / Kotoden,
    Kotosan, Shikoku Kotsu, and Koto Bus pages still need route-specific
    parsers before TAK airport access becomes fully playable.
- TAK / Kotosan Bus official Takamatsu Airport limousine parser.
  - Script: `scripts/ingest/collect_v5_takamatsu_kotosan_bus.py`
  - Source output: `data/v5_takamatsu_kotosan_official_bus_source.json`
  - Docs copy: `docs/data/v5_takamatsu_kotosan_official_bus_source.json`
  - Audit: `data/v5_takamatsu_kotosan_official_bus_audit.json`
  - Result: 2 active route directions parsed; 16 official trips extracted for
    the airport ⇔ Marugame / Sakaide / Utazu corridor. Rows explicitly marked
    運休 are skipped from active trips.
- Official-source overlap audit expanded to include TAK Kotosan Bus.
  - Result: 133 official routes checked; 4,104 official trips represented in
    source files; no likely GTFS duplicate overlap found after requiring an
    airport stop hit for duplicate candidates.
- TAK / Kotoden Bus official Takamatsu city airport limousine PDFs.
  - Script: `scripts/ingest/collect_v5_takamatsu_kotoden_bus.py`
  - Source output: `data/v5_takamatsu_kotoden_official_bus_source.json`
  - Docs copy: `docs/data/v5_takamatsu_kotoden_official_bus_source.json`
  - Audit: `data/v5_takamatsu_kotoden_official_bus_audit.json`
  - Result: 1 city-airport route parsed from official PDFs; 43 complete
    stop-coverage trips extracted across the current 2026-03-29 to 2026-05-31
    service window and the published 2026-06-01 to 2026-06-30 service window.
  - Note: the PDF table wraps a few dense rows across multiple text lines. The
    parser intentionally emits only rows where all stops are present on one
    extracted line, preserving limited-operation symbols for later calendar
    refinement instead of guessing wrapped rows.
- Official-source overlap audit expanded to include TAK Kotoden Bus.
  - Result: 134 official routes checked; 4,147 official trips represented in
    source files; no likely GTFS duplicate overlap found.
- TAK / Yonkoh official Awa-Ikeda airport bus parser.
  - Script: `scripts/ingest/collect_v5_takamatsu_yonkoh_bus.py`
  - Source output: `data/v5_takamatsu_yonkoh_official_bus_source.json`
  - Docs copy: `docs/data/v5_takamatsu_yonkoh_official_bus_source.json`
  - Audit: `data/v5_takamatsu_yonkoh_official_bus_audit.json`
  - Result: 1 official route parsed; 4 trips extracted for 阿波池田バス
    ターミナル ⇔ 高松空港 via 綾川駅.
- Official-source overlap audit expanded to include TAK Yonkoh.
  - Result: 135 official routes checked; 4,151 official trips represented in
    source files; no likely GTFS duplicate overlap found.
- TAK / Shikoku Chuo, Kanonji, Zentsuji, Marugame official airport PDF parser.
  - Script: `scripts/ingest/collect_v5_takamatsu_shikokuchuo_bus.py`
  - Source output: `data/v5_takamatsu_shikokuchuo_official_bus_source.json`
  - Docs copy: `docs/data/v5_takamatsu_shikokuchuo_official_bus_source.json`
  - Audit: `data/v5_takamatsu_shikokuchuo_official_bus_audit.json`
  - Result: 1 official PDF route parsed; 14 trips extracted for
    四国中央・観音寺・善通寺・丸亀 ⇔ 高松空港.
- Official-source overlap audit expanded to include TAK Shikoku Chuo / Seisan.
  - Result: 136 official routes checked; 4,165 official trips represented in
    source files.
  - Important overlap: this official PDF route matches an existing
    `西讃観光` GTFS airport route with full stop overlap. When promoted into
    the playable bundle, this official parser must replace or suppress the
    existing GTFS route rather than create duplicate ride choices.
- TAK / Kinku Bus official monthly timetable images.
  - Script: `scripts/ingest/collect_v5_takamatsu_kinku_bus_images.py`
  - Source output: `data/v5_takamatsu_kinku_official_bus_images.json`
  - Docs copy: `docs/data/v5_takamatsu_kinku_official_bus_images.json`
  - Audit: `data/v5_takamatsu_kinku_official_bus_images_audit.json`
  - Result: 4 official monthly/index pages cached and 6 uploaded timetable
    images cached.
  - Limitation: the operator publishes the active timetable as images, not
    machine-readable tables. These need OCR or a dedicated image-table parser
    before playable trips can be emitted.
- Official airport-bus runtime augmentation.
  - Script: `scripts/ingest/augment_v5_bus_bundle_with_official_sources.py`
  - Audit: `data/v5_official_bus_bundle_augmentation_audit.json`
  - Docs audit: `docs/data/v5_official_bus_bundle_augmentation_audit.json`
  - Current promoted routes: 105 routes, 3,673 trips, 22,286 stopTimes, 802 new
    official bus stops.
  - Promoted sources: 阪急観光バス ITM ⇔ 大阪空港／蛍池駅, ITM ⇔ 新大阪駅,
    ITM ⇔ 神戸三宮駅, 四国交通 阿波池田バスターミナル ⇔ 高松空港, and
    カリー観光 石垣空港 ⇔ 石垣港離島ターミナル. Later runtime batches added
    長崎空港 bus routes from the official Nagasaki monthly source, 45
    Keikyu Haneda airport-bus routes, 17 KATE/KIX official active routes, and
    all 13 ITM/Hankyu Kanko official active airport-limousine routes, and all
    14 CTS/Hokkaido Chuo official New Chitose Airport bus directions.
  - Runtime outputs rebuilt: `docs/data/v5_bus_gtfs_current_bundle.json.gz`,
    `docs/data/v5_bus_map_tiles/`, and `docs/data/v5_bus_planner_tiles/`.
  - Safety policy: routes marked as possible GTFS overlap are skipped; routes
    without at least two real coordinate-resolved stops and complete stopTimes
    are skipped. This prevents source parsers from creating duplicate or
    map-only bus choices.
  - Coordinate policy: unresolved official stops may be promoted only after a
    real geocode source is cached. The first such cache entry is
    石垣港離島ターミナル from OpenStreetMap/Nominatim.
  - HND/Keikyu parser support: the runtime augmenter now reads
    `timetables[].trips` and official timetable stop coordinates, not only
    top-level `trips`/`directions`.
  - KIX/KATE parser support: the KATE collector now attaches `stopName` and
    `stopIndex` to each `stopTime`, preserving Terminal 1/2 ordering even when
    the official page uses duplicate `KIX` stop codes.
  - Latest tile rebuild: 5,230 bus routes, 78,465 bus trips, 89,116 bus stops,
    111,493 walking connectors, and 27,453 active trips in Saturday planner
    tiles.
  - KIX/KATE active coverage: all 17 active KATE airport-bus routes are now
    promoted into the playable runtime bundle. The final Wakayama route was
    unblocked with real coordinates for Wakauraguchi, Nisseki Iryo Center mae,
    Wakayamajo mae, and Mikimachi Shintori.
  - ITM/Hankyu Kanko active coverage: all 13 parsed active Osaka Itami airport
    limousine routes are now promoted into the playable runtime bundle. The
    remaining ten routes were unblocked by normalizing station-adjacent stop
    names such as JR難波駅（OCAT）, 近鉄上本町駅, 大和西大寺駅南口,
    四条河原町, 阪神甲子園駅, and by adding real coordinates for hotel,
    venue, and highway-stop labels such as 大阪マルビル, ホテル阪神,
    奈良県コンベンションセンター, 久留美, 淡河, and
    ユニバーサル・スタジオ・ジャパン.
  - CTS/Hokkaido Chuo parser support: the official bus augmenter now inherits
    top-level `operatorName` and `airportIata` fields from source files and
    generates stable fallback route codes from `routeNumber + direction` when
    official route entries have no explicit code. All 14 Chuo Bus New Chitose
    directions are now playable after adding high-confidence coordinates for
    Sapporo hotel, road-junction, shopping-center, subway-adjacent, and Otaru
    stops from OSM/Nominatim and existing rail station-group aliases.
  - HND/Keikyu active coverage: 45 Haneda/Keikyu official airport-bus routes
    are now playable. The latest unblock added explicit aliases for clear
    station-terminal labels such as 蘇我駅東口, 渋谷駅（渋谷フクラス）,
    横浜駅（YCAT）, and JR千葉駅（西口）.
  - 2026-05-18 runtime unblock: 10 additional official airport-bus routes are
    now playable after adding high-confidence stop aliases/coordinates for
    HND/Keikyu Karuizawa, Yokohama/Yamashita, Kawaguchiko, and Tateyama-area
    routes; TAK Kotoden/Kotosan city and Marugame stops; and UKB Kobe Airport
    ⇔ Tokushima bilingual stops.
  - 2026-05-18 KMI unblock: the Miyazaki Airport source was upgraded from
    airport-page summary departures to Miyazaki Kotsu official route PDFs.
    宮崎駅, 西都城, 飫肥・日南, and シーガイア airport bus corridors are now
    playable with complete endpoint/airport stopTimes. Remaining blockers are
    now 1 intentional GTFS-overlap Takamatsu route and 20 no-trip/cancelled
    source routes.
  - 2026-05-18 KIJ unblock: the Niigata Airport source was upgraded from
    cached PDFs to a playable official direct-bus route. 新潟駅 ⇔ 新潟空港 is
    now playable with 49 direct limousine-bus trips and ¥470 adult fare. Local
    airport buses via 万代シテイ remain source-cached until complete
    intermediate stop-times are normalized.
  - 2026-05-18 ISG route 10 unblock: the Ishigaki Airport 東運輸 source now
    promotes 系統⑩ アートホテル・ANAインターコンチネンタル経由空港線 from the official
    PDF timetable. The playable runtime adds 1 route, 10 trips, 275 stopTimes,
    and 28 stops. Stop-times come from the official PDF; route stop coordinates
    use NAVITIME stop pages where the PDF has no machine-readable coordinate
    data. 石垣港離島ターミナル and 石垣空港 reuse the existing terminal/airport
    anchors to avoid duplicate stop nodes.
  - 2026-05-18 remaining-source unblock: the Ishigaki Airport 東運輸 source now
    also promotes 系統④ 平得・大浜・白保経由空港線 from the official PDF
    timetable. The playable runtime adds 1 route, 58 trips, 1,524 stopTimes,
    and 29 newly created official stops/reused anchors. Stop-times come from
    the official PDF; route stop coordinates use NAVITIME stop pages where the
    PDF has no machine-readable coordinate data. The same pass promotes KIJ
    万代シテイ経由 local buses as endpoint-playable trips. Remaining
    non-playable/not-added sources are only 1 intentional Takamatsu
    GTFS-overlap route and 20 empty/no-trip/cancelled official sources.
  - 2026-05-18 14:54:38 PDT nationwide gap continuation: the current airport
    access audit showed this work is not nationally complete yet. It now
    reports 29 covered airports, 2 airports with nearby non-airport-class bus
    stops, 4 airports with stops only in the 5 km review radius, and 41
    airports with no bus stop within 5 km. Added OIT / Oita Airport as the next
    high-flight-volume missing-airport target.
  - OIT / Oita Kotsu official Airliner HTML timetable.
    - Script: `scripts/ingest/collect_v5_oita_airport_bus.py`
    - Source output: `data/v5_oita_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_oita_airport_official_bus_source.json`
    - Audit: `data/v5_oita_airport_official_bus_audit.json`
    - Result: 1 official airport-bus route normalized for
      エアライナー 大分・別府 ⇔ 大分空港, with 84 trips, 674 stopTimes, 15
      stops, and current release-period calendars for 2026-05-01 through
      2026-05-31. Stop-times come from the official 大分交通 HTML timetable;
      coordinates use NAVITIME stop pages only as coordinate references.
    - Runtime outputs rebuilt: total bus coverage is now 5,234 routes, 78,657
      trips, 89,188 stops, 97,891 map features, 450 map tiles, 27,621 active
      planner trips, 708,649 indexed planner stopTimes, and 111,519 walking
      connectors.
  - 2026-05-18 15:21:59 PDT MYJ / Matsuyama Airport continuation:
    - Script: `scripts/ingest/collect_v5_matsuyama_airport_bus.py`
    - Source output: `data/v5_matsuyama_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_matsuyama_airport_official_bus_source.json`
    - Audit: `data/v5_matsuyama_airport_official_bus_audit.json`
    - Result: 1 official airport-bus route normalized for 松山空港リムジンバス,
      with 91 trips, 440 stopTimes, 7 stops, and current release-period
      calendars for 2026-05-01 through 2026-05-31. Stop-times come from the
      official 伊予鉄 bus HTML timetable; coordinates use NAVITIME stop pages
      only as coordinate references.
    - Runtime outputs rebuilt: total bus coverage is now 5,235 routes, 78,748
      trips, 89,195 stops, 97,899 map features, 452 map tiles, 27,712 active
      planner trips, 709,089 indexed planner stopTimes, and 111,591 walking
      connectors. Airport-class coverage increased to 30 airports; no-5km-stop
      airports decreased to 40.
  - 2026-05-18 15:46:50 PDT HIJ / Hiroshima Airport continuation:
    - Script: `scripts/ingest/collect_v5_hiroshima_airport_bus.py`
    - Source output: `data/v5_hiroshima_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_hiroshima_airport_official_bus_source.json`
    - Audit: `data/v5_hiroshima_airport_official_bus_audit.json`
    - Result: 2 official airport-bus routes normalized for
      広島バスセンター・中筋駅 ⇔ 広島空港 and 広島駅新幹線口 ⇔ 広島空港,
      with 159 trips, 374 stopTimes, 4 source stops, and release-period
      calendars for 2026-03-29 through 2026-06-30. Stop-times come from the
      official Hiroshima Airport HTML timetable pages; coordinates use
      NAVITIME stop pages only as coordinate references.
    - Runtime outputs rebuilt: total bus coverage is now 5,237 routes, 78,907
      trips, 89,200 stops, 97,906 map features, 454 map tiles, 27,871 active
      planner trips, 709,463 indexed planner stopTimes, and 111,626 walking
      connectors. Airport-class coverage increased to 31 airports; no-5km-stop
      airports decreased to 39.
  - 2026-05-18 16:06:53 PDT HKD / Hakodate Airport continuation:
    - Script: `scripts/ingest/collect_v5_hakodate_airport_bus.py`
    - Source output: `data/v5_hakodate_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_hakodate_airport_official_bus_source.json`
    - Audit: `data/v5_hakodate_airport_official_bus_audit.json`
    - Result: 3 current Hakodate Bus airport-departure routes normalized for
      5・5A系統, 快速8系統, and 96系統 from 函館空港 to 函館駅前, with 38 trips
      and 76 stopTimes. Departure times come from the current Hakodate Bus
      official timetable API generation `20260511`; endpoint arrival times use
      the official airport/access page runtime estimates because the API page
      exposes departure timetables by stop, not full intermediate stop-time
      traces.
    - Runtime outputs rebuilt: total bus coverage is now 5,240 routes, 78,945
      trips, 89,206 stops, 97,915 map features, 456 map tiles, 27,891 active
      planner trips, 709,503 indexed planner stopTimes, and 111,665 walking
      connectors. Airport-class coverage increased to 32 airports; no-5km-stop
      airports decreased to 38.
    - Source limitation: Hakodate Teisan's public current page was not available
      for the May 2026 planner date, so its older February 2026 PDF was not
      promoted as current playable service.
  - 2026-05-18 16:39:05 PDT AXT / Akita Airport continuation:
    - Script: `scripts/ingest/collect_v5_akita_airport_bus.py`
    - Source output: `data/v5_akita_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_akita_airport_official_bus_source.json`
    - Audit: `data/v5_akita_airport_official_bus_audit.json`
    - Result: 1 official airport-limousine route normalized for 秋田駅西口
      ⇔ 秋田空港, with 37 trips, 74 stopTimes, and a ¥1200 adult fare. Times
      come from the official 秋田中央交通 AJAX timetable for 2026-05-01 through
      2026-05-31.
    - Runtime outputs rebuilt: total bus coverage is now 5,241 routes, 78,982
      trips, 89,208 stops, 97,918 map features, 457 map tiles, 27,928 active
      planner trips, 709,577 indexed planner stopTimes, and 111,667 walking
      connectors. Airport-class coverage increased to 33 airports; no-5km-stop
      airports decreased to 37.
  - 2026-05-18 17:06:28 PDT MMY / Miyako Airport continuation:
    - Script: `scripts/ingest/collect_v5_miyako_airport_bus.py`
    - Source output: `data/v5_miyako_airport_official_bus_source.json`
    - Docs copy: `docs/data/v5_miyako_airport_official_bus_source.json`
    - Audit: `data/v5_miyako_airport_official_bus_audit.json`
    - Result: 1 endpoint-playable airport-liner route normalized for 宮古空港
      ⇔ みやこ下地島空港, with 8 trips and 16 stopTimes. Times come from the
      Miyakojima City tourism route page; airport coordinates come from the V5
      airport map.
    - Runtime outputs rebuilt: total bus coverage is now 5,242 routes, 78,990
      trips, 89,210 stops, 97,921 map features, 459 map tiles, 27,936 active
      planner trips, 709,593 indexed planner stopTimes, and 111,669 walking
      connectors. Airport-class coverage increased to 35 airports because the
      route covers both MMY and SHI; no-5km-stop airports decreased to 35.
    - Source limitation: intermediate stops from the public page are not yet
      promoted because their stop coordinates are not normalized.

## Official Source Seeds

- HND: `https://tokyo-haneda.com/en/access/bus/`
- CTS: `https://www.hokkaido-airports.com/en/new-chitose/access/bus/`
- CTS operator: `https://www.chuo-bus.co.jp/airport.en/`
- ITM: `https://www.osaka-airport.co.jp/en/access/from-airport/bus`
- KIX: `https://www.kansai-airport.or.jp/en/access/from-airport/bus`
- KIX operator: `https://www.kate.co.jp/en/`

## Parser Requirements

Each official parser should output the same normalized bus model as the GTFS
bundle:

- `busAgencyId`
- `busStopId`
- `busRouteId`
- `busTripId`
- `busServiceCalendarId`
- `stops`
- `routes`
- `trips`
- `stopTimes`
- `fareAttributes`
- `fareRules`
- `walkingConnectors`

Do not add airport-bus data as hardcoded map-only geometry. It must be playable:
departure times, stop order, fares, and airport/rail walking connectors all
need to exist.

## Playability Requirement

Bus data collection is not considered finished when a source file is created.
For each collected bus source, the expected endpoint is:

- source parser output with real stop names, stop order, trip times, calendar
  policy, and fares when available;
- overlap audit against existing GTFS / official sources;
- promotion into `v5_bus_gtfs_current_bundle.json.gz` when every trip has at
  least two real stopTimes and every stop has a real coordinate;
- rebuilt bus map and planner tiles under `docs/data/`;
- audit entry explaining any source that remains blocked.

Blocked data should stay visible in audit/backlog, but it should not be counted
as playable. Current common blockers are missing coordinates, duplicate
GTFS/official overlap, image-only/OCR-only timetables, stopCode-only rows,
summary departure times without arrival/stop sequence, and unresolved service
calendar rules.

## Data Conflict Axiom

When adding an official parser, check overlap with the existing GTFS source
layer before merging:

- Same operator + same route + similar stop sequence should not create duplicate
  ride choices.
- Official airport parser should win over stale or incomplete GTFS when both
  exist.
- If both sources are valid but represent different seasonal calendars, keep
  both only when service dates do not overlap.

## IWK / Iwakuni Kintaikyo Airport

- 2026-05-19 14:17:26 PDT - Added IWK from the official Iwakuni Kintaikyo Airport access-bus PDF and airport access HTML.
- Remaining airport-bus gap after promotion:
  - Strict no-stop-within-5km gaps: 30
  - Review-inclusive gaps: 36
- Source:
  - Official Iwakuni Kintaikyo Airport bus access page: `https://www.iwakuni-airport.jp/access/access-bus/`
  - Official timetable PDF: `https://www.iwakuni-airport.jp/cms/wp-content/themes/iwakuni-airport/images/download/timetable_20260329.pdf`
  - Current section effective 2026-03-29 through 2026-10-24.
- Parser:
  - `scripts/ingest/collect_v5_iwakuni_airport_bus.py`
- Output:
  - `data/v5_iwakuni_airport_official_bus_source.json`
  - `docs/data/v5_iwakuni_airport_official_bus_source.json`
  - `data/v5_iwakuni_airport_official_bus_audit.json`
- Normalized gameplay data:
  - Routes: 岩国駅東口線 and 広島バスセンター線 via 錦帯橋
  - Trips: 16
  - StopTimes: 48
  - Endpoint/intermediate stops: 岩国駅東口, シンフォニア, 岩国錦帯橋空港, 錦帯橋, 広島バスセンター
  - Fares: ¥200 for 岩国駅東口, ¥1000 for 広島バスセンター, with 錦帯橋 listed inside the official route context.
  - Direction split: 9 to airport, 7 from airport
- Checks:
  - Targeted overlap audit: both route families `no_gtfs_overlap_found`
  - Airport access audit: IWK is now `covered_by_gtfs_airport_bus`
- Runtime after promotion:
  - Total bus routes: 5,251
  - Total bus trips: 79,167
  - Total bus stops: 89,230
  - Active planner bus trips: 28,087
  - Indexed planner stopTimes: 709,911
  - Planner walking connectors: 111,715

## OKJ / Okayama Momotaro Airport

- 2026-05-19 14:36:03 PDT - Added OKJ from the official Okayama Momotaro Airport bus access timetable.
- Remaining airport-bus gap after promotion:
  - Strict no-stop-within-5km gaps: 29
  - Review-inclusive gaps: 35
- Source:
  - Official Okayama Momotaro Airport bus page: `https://www.okayama-airport.org/access/bus`
  - Current section effective 2026-03-29 through 2026-06-30.
- Parser:
  - `scripts/ingest/collect_v5_okayama_airport_bus.py`
- Output:
  - `data/v5_okayama_airport_official_bus_source.json`
  - `docs/data/v5_okayama_airport_official_bus_source.json`
  - `data/v5_okayama_airport_official_bus_audit.json`
- Normalized gameplay data:
  - Routes: 岡山駅西口線 and 倉敷駅北口線
  - Trips: 45
  - StopTimes: 90
  - Endpoint stops: 岡山駅西口, 倉敷駅北口, 岡山桃太郎空港
  - Fares: ¥1000 for 岡山駅西口 and ¥1400 for 倉敷駅北口
  - Direction split: 22 to airport, 23 from airport
  - Service windows: daily rows plus official current/future special markers for the 2026-03-29 to 2026-06-30 timetable.
- Checks:
  - Targeted overlap audit: both route families `no_gtfs_overlap_found`
  - Airport access audit: OKJ is now `covered_by_gtfs_airport_bus`
- Runtime after promotion:
  - Total bus routes: 5,253
  - Total bus trips: 79,212
  - Total bus stops: 89,234
  - Active planner bus trips: 28,129
  - Indexed planner stopTimes: 709,995
  - Planner walking connectors: 111,731

## KUH / Kushiro Airport

- 2026-05-19 15:36:57 PDT - Added KUH from the official Akan Bus Kushiro Airport shuttle PDF.
- Remaining airport-bus gap after promotion:
  - Strict no-stop-within-5km gaps: 28
  - Review-inclusive gaps: 34
- Source:
  - Official Akan Bus airport page: `https://www.akanbus.co.jp/airport/`
  - Official timetable script: `https://www.akanbus.co.jp/airport/time-table.cgi`
  - Official current PDF: `https://www.akanbus.co.jp/airport/data/80_01.pdf`
  - Current section effective 2026-04-24 through 2026-05-31.
- Parser:
  - `scripts/ingest/collect_v5_kushiro_airport_bus.py`
- Output:
  - `data/v5_kushiro_airport_official_bus_source.json`
  - `docs/data/v5_kushiro_airport_official_bus_source.json`
  - `data/v5_kushiro_airport_official_bus_audit.json`
- Normalized gameplay data:
  - Route: 釧路空港連絡バス 釧路駅前 ⇔ たんちょう釧路空港
  - Fixed-clock trips emitted: 13 city-to-airport trips
  - StopTimes: 26
  - Endpoint stops: 釧路駅前, たんちょう釧路空港
  - Fare: ¥1200
  - Limitation: airport-to-city service is officially arrival-connected and departs about 10 to 25 minutes after each plane arrival, so it is documented in source notes but not emitted as fixed-clock trips until V5 supports flexible airport-arrival bus departures.
- Checks:
  - Targeted overlap audit: `no_gtfs_overlap_found`
  - Airport access audit: KUH is now `covered_by_gtfs_airport_bus`
- Runtime after promotion:
  - Total bus routes: 5,254
  - Total bus trips: 79,225
  - Total bus stops: 89,236
  - Active planner bus trips: 28,142
  - Indexed planner stopTimes: 710,021
  - Planner walking connectors: 111,733

## MMB / Memanbetsu Airport

- 2026-05-19 15:54:05 PDT - Added MMB from the official Abashiri Bus Memanbetsu Airport line PDFs.
- Remaining airport-bus gap after promotion:
  - Strict no-stop-within-5km gaps: 27
  - Review-inclusive gaps: 33
- Source:
  - Official Abashiri Bus PDF to airport: `https://www.abashiribus.com/jikoku/mmbR08.05.01_1.pdf`
  - Official Abashiri Bus PDF from airport: `https://www.abashiribus.com/jikoku/mmbR08.05.01_2.pdf`
  - Current section effective 2026-05-01 through 2026-05-31.
- Parser:
  - `scripts/ingest/collect_v5_memanbetsu_airport_bus.py`
- Output:
  - `data/v5_memanbetsu_airport_official_bus_source.json`
  - `docs/data/v5_memanbetsu_airport_official_bus_source.json`
  - `data/v5_memanbetsu_airport_official_bus_audit.json`
- Normalized gameplay data:
  - Route: 女満別空港線 網走駅前 ⇔ 女満別空港
  - Trips: 19
  - StopTimes: 38
  - Endpoint stops: 網走駅前, 女満別空港
  - Fare: ¥1050
  - Direction split: 9 to airport, 10 from airport
- Checks:
  - Targeted overlap audit: `no_gtfs_overlap_found`
  - Airport access audit: MMB is now `covered_by_gtfs_airport_bus`
- Runtime after promotion:
  - Total bus routes: 5,255
  - Total bus trips: 79,244
  - Total bus stops: 89,238
  - Active planner bus trips: 28,161
  - Indexed planner stopTimes: 710,059
  - Planner walking connectors: 111,737
