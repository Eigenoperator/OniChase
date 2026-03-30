# YAMANOTE TIMETABLE EXTRACTION

## Purpose

This document explains how to obtain real Yamanote Line timetable data from JR East official timetable pages and transform it into train-instance records for the game.

## Main Finding

JR East official timetable data appears to expose two useful layers:

1. **Station timetable pages**
2. **Train detail pages**

This is exactly what we need.

The station timetable page tells us:

- station
- line
- direction
- day type
- departure times

The train detail page tells us:

- one concrete train run
- train number
- station-by-station arrival / departure times

This means we do **not** need to reconstruct every train instance only by guessing across multiple station departure tables. The site structure appears to already expose train-instance detail pages.

## Official Source Entry Points

### Timetable top

- `https://timetables.jreast.co.jp/en/index.html`

This is the official JR East timetable search entry point.

### Station timetable list page

Example:

- `https://timetables.jreast.co.jp/en/timetable/list1248.html`

Observed on:

- Hamamatsucho Station

This page lists:

- route name
- direction
- weekday link
- saturday/holiday link

Example observed lines:

- Yamanote Line for Shinagawa / Shibuya (Clockwise)
- Yamanote Line for Tokyo / Ueno (Counterclockwise)

### Station timetable detail page

Example:

- `https://timetables.jreast.co.jp/en/2602/timetable/tt1039/1039120.html`

Observed on:

- Tokyo Station, Yamanote Line, Counterclockwise, Weekdays

This page contains:

- hour buckets
- linked departure minutes
- some extra symbols for specific departures

Important observation:

- each minute entry is a clickable link

### Train detail page

Observed JR East page pattern:

- `https://timetables.jreast.co.jp/en/.../train/...html`

Example pattern confirmed from JR East result pages:

- train detail pages titled `Timetable (List of Stations)`
- contain `Train number`
- contain station-by-station arrival / departure records

Even though the specific Yamanote train-detail URLs were not directly fetched through the tool cache, the station timetable pages clearly link minute entries to `/train/...html` pages, and JR East train-detail pages in the same system expose exactly the data shape we need.

## Extraction Strategy

## Step 1: Build Canonical Station List

Use:

- `data/yamanote_stations.json`

This gives us:

- all 30 real Yamanote stations
- stable station IDs
- multilingual display names

## Step 2: Discover Station Timetable Pages

For each Yamanote station:

1. locate the station timetable list page
2. identify the two Yamanote directions:
   - clockwise
   - counterclockwise
3. open the weekday timetable page for each direction

This gives us:

- all departure minute entries for that station/direction/day type

## Step 3: Follow Minute Links To Train Detail Pages

From each station timetable detail page:

1. collect every clickable minute entry
2. resolve its linked `/train/...html` URL
3. open the train detail page

This gives us:

- one concrete train run
- train number
- stop list
- arrival/departure times
- sometimes track/platform

## Step 4: Normalize Into Train Instances

Store each fetched train-detail page as one `TrainInstance`.

Recommended normalized shape:

```ts
type TrainInstance = {
  id: string;
  train_number: string;
  direction: "clockwise" | "counterclockwise";
  service_day: "weekday";
  source_station_id: string;
  source_departure_hhmm: string;
  service_instance_id?: string;
  stop_times: {
    station_id: string;
    line_id: string;
    loop_pass_index?: number;
    arrival_hhmm?: string;
    departure_hhmm?: string;
    track?: string;
    sequence: number;
  }[];
  source_url: string;
};
```

Modeling note:

- `TrainInstance` should not be permanently bound to a single line field
- line identity belongs on each stop-time row so future through-services across multiple lines remain representable
- on loop lines, repeated stations must be preserved inside one train instance rather than forcing a cut at one full lap

## Loop-Line Interpretation

For Yamanote specifically:

- one train instance should be stored as one continuous ordered stop-time list
- if the same station appears twice, keep both rows
- distinguish them by `sequence` and `loop_pass_index`
- do not split a train only because it completed one loop if the official service record continues

## Step 5: Deduplicate

Because the same train run may be reachable from multiple station timetable pages, deduplication is required.

Recommended dedupe keys:

1. `train_number` plus first departure time
2. if needed, full ordered stop signature

Best-case dedupe key:

- `train_number`

Fallback dedupe key:

- `first station + first departure + station sequence hash`

## Practical Recommendation

For the first implementation pass, do **not** scrape all 30 stations first.

Instead:

1. pick one station with both directions clearly exposed
2. fetch one weekday direction page
3. verify that minute links consistently resolve to train detail pages
4. parse 5 to 10 trains end-to-end
5. confirm the dedupe strategy
6. only then scale up to the full Yamanote line

Good first stations:

- Tokyo
- Ueno
- Hamamatsucho

These are easy to find on JR East official pages and have clear Yamanote timetable entries.

## Known Risks

### 1. Link traversal complexity

Minute links likely require careful HTML parsing and may vary slightly by locale or date.

### 2. Date sensitivity

JR East train detail pages include operating date context. We should pin one weekday date during extraction.

### 3. Symbol-marked departures

Some station timetable entries show suffix symbols such as special markers. These may encode short-turn or non-full-loop services and must not be ignored.

### 4. Direction naming mismatch

The site may use:

- clockwise / counterclockwise
- inner / outer semantics in Japanese

We should store both raw label and normalized direction.

## Recommended Immediate Code Plan

1. write a Yamanote station validator
2. write a small discovery script for one station timetable page
3. write a parser for minute-entry links
4. write a parser for one train detail page
5. normalize into `TrainInstance`

## Current Conclusion

The JR East official timetable system appears sufficient for our needs.

The most promising extraction path is:

`station timetable list` -> `direction/day timetable page` -> `minute link` -> `train detail page`

This is the correct path to build a real Yamanote train-instance timetable database for the game.
