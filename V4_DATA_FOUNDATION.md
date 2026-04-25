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

Current generated counts:

- Physical stations: `10235`
- Station groups: `9048`
- Track centerlines: `21932`
- Operators: `178`
- Same-name split names: `427`
- Line coverage warnings: `0`

## Regenerate

```bash
cd /home/xincheng/toy/Chase
python3 scripts/ingest/build_v4_japan_physical_map.py
python3 scripts/ingest/audit_v4_station_identity.py
```

## Station Identity V2

- `physicalStations` preserve real N02 station geometry and coordinates.
- `stationGroups` are gameplay/interchange identity, not fake map coordinates.
- N02 `N02_005g` group code is used first for station grouping.
- Same-name stations are not globally collapsed; names like `市役所前`, `大和`, `赤坂`, and `有明` can remain separate groups.
- If a source station has no group code later, fallback grouping must use both station name and local position.
