# OniChase V5 Bus Collection Backlog

Generated from the current V5 bus audits on `2026-05-16`.

## Current Playable Source Layer

- GTFS bundle: 454 successfully parsed feeds.
- Bus stops: 88,213.
- Bus routes: 5,114.
- Bus trips: 74,536.
- Stop times: 2,243,003.
- Runtime planner tiles: 374 tiles.
- Saturday active trips in planner tiles: 23,580.
- Walking connectors: 107,349.
- Routes with GTFS fare-rule coverage: 4,536.

## Highest Priority Gap

Airport access is the most important missing data family because V5 flight
gameplay depends on reliable airport ground access.

Current airport access audit:

- 17 airports covered by GTFS airport-class bus routes.
- 2 airports have nearby GTFS bus stops but no airport-class route.
- 4 airports have GTFS bus stops only within the wider 5 km review radius.
- 53 airports have no GTFS bus stop within 5 km in this first source layer.

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
| 10 | KIJ | no GTFS stop within 5 km | Niigata Airport access bus operators |

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
  - Result: 2 official PDFs cached, but both appear image/vector based and do
    not expose extractable timetable text through `pdftotext`. They need OCR or
    a different structured source before route normalization.
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

## Data Conflict Axiom

When adding an official parser, check overlap with the existing GTFS source
layer before merging:

- Same operator + same route + similar stop sequence should not create duplicate
  ride choices.
- Official airport parser should win over stale or incomplete GTFS when both
  exist.
- If both sources are valid but represent different seasonal calendars, keep
  both only when service dates do not overlap.
