# V4 Data Foundation

This is the first `v4` data slice: nationwide real physical rail geometry plus `station_identity_v2`.

## Source

- Local source: `data/raw_n02_24/UTF-8/N02-24_Station.geojson`
- Local source: `data/raw_n02_24/UTF-8/N02-24_RailroadSection.geojson`
- Source family: MLIT N02 railway data, 2024 edition.
- The raw N02 directory is intentionally ignored by git; keep or redownload it before regenerating the bundle.
- Land outline source: geoBoundaries `gbOpen/JPN/ADM0`, fetched by `scripts/ingest/build_v4_land_outline.py`.
- Prefecture note source: geoBoundaries `gbOpen/JPN/ADM1`, cached under ignored `data/raw_boundaries/`.

## Outputs

- `data/v4_japan_physical_map.json.gz`
- `data/v4_station_identity_audit.json`
- `data/v4_nationwide_line_inventory.json`
- `data/v4_track_continuity_audit.json`
- `docs/data/v4_maplibre/japan_land.geojson`
- `docs/data/v4_maplibre/japan_land_overview.geojson`
- `docs/data/v4_maplibre/track_overview.geojson`
- `docs/data/v4_maplibre/track_centerlines.geojson`
- `docs/data/v4_maplibre/station_groups.geojson`
- `docs/data/v4_maplibre/station_labels.geojson`
- `docs/data/v4_maplibre/physical_stations.geojson`
- `docs/data/v4_maplibre/line_inventory.json`
- `docs/data/v4_maplibre/manifest.json`
- `docs/v4.html`

Current generated counts:

- Physical stations: `10235`
- Station groups: `9048`
- Track centerlines: `21932`
- Operators: `178`
- Same-name split names: `427`
- Line coverage warnings: `0`
- Nationwide operator-line pairs: `596`
- Unique line names: `552`
- Track continuity warnings: `12` multi-component operator-line pairs

## Regenerate

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/build_v4_japan_physical_map.py
python3 scripts/ingest/audit_v4_station_identity.py
python3 scripts/ingest/build_v4_land_outline.py
python3 scripts/ingest/build_v4_line_inventory.py
python3 scripts/ingest/build_v4_maplibre_sources.py
python3 scripts/ingest/audit_v4_track_continuity.py
```

## Station Identity V2

- `physicalStations` preserve real N02 station geometry and coordinates.
- `stationGroups` are gameplay/interchange identity, not fake map coordinates.
- N02 `N02_005g` group code is used first for station grouping.
- Same-name stations are not globally collapsed; names like `市役所前`, `大和`, `赤坂`, and `有明` can remain separate groups.
- `physicalStations` and `stationGroups` include `prefecture*` fields plus `locationNote` to disambiguate same-name stations without changing station identity.
- If a source station has no group code later, fallback grouping must use both station name and local position.

## MapLibre Sources

`docs/data/v4_maplibre/manifest.json` is the public entry point for browser-side loading.

- `track_centerlines.geojson`: nationwide physical rail LineString features.
- `track_overview.geojson`: simplified low-zoom operator-line geometry.
- `japan_land.geojson`: high-detail Japan outline only; the v4 viewer does not use a land-fill layer.
- `japan_land_overview.geojson`: lighter low-zoom Japan outline.
- `station_groups.geojson`: gameplay/interchange identity points.
- `station_labels.geojson`: v3-shaped station label source used by the v4 viewer; includes `location_note`.
- `physical_stations.geojson`: real physical station points.
- `line_inventory.json`: all current nationwide operator-line pairs.

The first export is GeoJSON so it can be loaded directly by MapLibre during development. Low zoom uses `track_overview.geojson`, but it fades out by zoom `7.65`; high-detail `track_centerlines.geojson` takes over from zoom `7.55`, and physical-station dots are loaded lazily by the viewer. Later performance work should convert this same layer contract into vector tiles or PMTiles.

The first public viewer is `https://eigenoperator.github.io/OniChase/v4.html`. It shows the nationwide physical track layer, station groups, optional high-zoom physical stations, and a searchable operator-line inventory with per-line geometry highlighting.

Track-continuity audit outputs remain internal generated artifacts; no public continuity-review page is exposed.
