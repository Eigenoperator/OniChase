# V4 Data Foundation

This is the first `v4` data slice: nationwide real physical rail geometry plus `station_identity_v2`.

## Source

- Local source: `data/raw_n02_24/UTF-8/N02-24_Station.geojson`
- Local source: `data/raw_n02_24/UTF-8/N02-24_RailroadSection.geojson`
- Source family: MLIT N02 railway data, 2024 edition.
- The raw N02 directory is intentionally ignored by git; keep or redownload it before regenerating the bundle.

## Outputs

- `data/v4_japan_physical_map.json.gz`
- `data/v4_station_identity_audit.json`
- `data/v4_nationwide_line_inventory.json`
- `docs/data/v4_maplibre/track_centerlines.geojson`
- `docs/data/v4_maplibre/station_groups.geojson`
- `docs/data/v4_maplibre/physical_stations.geojson`
- `docs/data/v4_maplibre/line_inventory.json`
- `docs/data/v4_maplibre/manifest.json`

Current generated counts:

- Physical stations: `10235`
- Station groups: `9048`
- Track centerlines: `21932`
- Operators: `178`
- Same-name split names: `427`
- Line coverage warnings: `0`
- Nationwide operator-line pairs: `596`
- Unique line names: `552`

## Regenerate

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/build_v4_japan_physical_map.py
python3 scripts/ingest/audit_v4_station_identity.py
python3 scripts/ingest/build_v4_line_inventory.py
python3 scripts/ingest/build_v4_maplibre_sources.py
```

## Station Identity V2

- `physicalStations` preserve real N02 station geometry and coordinates.
- `stationGroups` are gameplay/interchange identity, not fake map coordinates.
- N02 `N02_005g` group code is used first for station grouping.
- Same-name stations are not globally collapsed; names like `市役所前`, `大和`, `赤坂`, and `有明` can remain separate groups.
- If a source station has no group code later, fallback grouping must use both station name and local position.

## MapLibre Sources

`docs/data/v4_maplibre/manifest.json` is the public entry point for browser-side loading.

- `track_centerlines.geojson`: nationwide physical rail LineString features.
- `station_groups.geojson`: gameplay/interchange identity points.
- `physical_stations.geojson`: real physical station points.
- `line_inventory.json`: all current nationwide operator-line pairs.

The first export is GeoJSON so it can be loaded directly by MapLibre during development. Later performance work should convert this same layer contract into vector tiles or PMTiles.
