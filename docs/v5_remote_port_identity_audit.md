# V5 Remote Port Identity Audit

This audit reviews the ports that are already classified as remote/small-island
2 km access gaps. It does not add connectors. It only flags cases where
the port identity or coordinate still looks risky.

## Summary

- `remotePortCount`: 111
- `needsIdentityReview`: 36
- `watch`: 52
- `ok`: 23
- `duplicateCoordinateGroups`: 3
- `playableAffectedNeedsReview`: 29

## Needs Identity Review

- **黒島** (24.2534441, 124.0014719), 32 sailings: OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **宗方港** (34.2031092, 132.9428741), 22 sailings: OSM/Nominatim display does not clearly overlap the port name
- **古仁屋** (28.1456875, 129.3086902), 21 sailings: OSM/Nominatim display does not clearly overlap the port name
- **佐合島** (33.8751429, 132.0667164), 20 sailings: OSM/Nominatim display does not clearly overlap the port name
- **神浦** (33.2548582, 129.0946886), 19 sailings: OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **島浦** (33.9730659, 132.6301301), 16 sailings: same coordinate shared by 2 port names: 島浦, 中島; weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **細島港** (34.3607302, 133.1371422), 16 sailings: OSM/Nominatim display does not clearly overlap the port name
- **湊** (33.1229254, 139.8168369), 14 sailings: OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **玄界島** (33.6824326, 130.2351162), 14 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **伊保田港** (33.9442177, 132.4391337), 12 sailings: same coordinate shared by 2 port names: 伊保田港, 伊保田
- **出羽島** (33.6363945, 134.4243816), 12 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **相島** (34.5016633, 131.280415), 12 sailings: OSM/Nominatim display does not clearly overlap the port name
- **馬島** (33.9651826, 130.8546119), 12 sailings: OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **家浦** (34.4900759, 134.0609824), 10 sailings: OSM/Nominatim display does not clearly overlap the port name
- **岡村港** (34.1844812, 132.8839061), 10 sailings: OSM/Nominatim display does not clearly overlap the port name
- **牛島** (33.8593953, 132.0069054), 10 sailings: OSM/Nominatim display does not clearly overlap the port name
- **伊保田** (33.9442177, 132.4391337), 8 sailings: same coordinate shared by 2 port names: 伊保田港, 伊保田; OSM/Nominatim display does not clearly overlap the port name
- **口永良部島港** (30.464, 130.191), 8 sailings: weak geocoder source still marked needs_precise_port_review
- **情島** (33.9584653, 132.4791606), 8 sailings: same coordinate shared by 2 port names: 情島, 青島; OSM/Nominatim display does not clearly overlap the port name
- **与路** (28.0454688, 129.1665601), 7 sailings: OSM/Nominatim display does not clearly overlap the port name
- **嵯峨島** (32.728348, 128.6010501), 6 sailings: OSM/Nominatim display does not clearly overlap the port name
- **斎島** (34.1196117, 132.7936031), 6 sailings: OSM/Nominatim display does not clearly overlap the port name
- **藍島** (33.9883219, 130.8183732), 6 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **貝津** (32.7142323, 128.6532677), 6 sailings: OSM/Nominatim display does not clearly overlap the port name
- **島間港** (30.414, 130.948), 4 sailings: weak geocoder source still marked needs_precise_port_review
- **片島** (30.8305538, 129.9064709), 4 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **青島** (33.9584653, 132.4791606), 4 sailings: same coordinate shared by 2 port names: 情島, 青島; weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **黄島** (32.5706359, 128.9045721), 4 sailings: OSM/Nominatim display does not clearly overlap the port name
- **小呂島** (33.8632695, 130.0349724), 2 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **中島** (33.9730659, 132.6301301), 0 sailings: same coordinate shared by 2 port names: 島浦, 中島; OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **嘉島** (33.2287201, 132.364022), 0 sailings: OSM/Nominatim display does not clearly overlap the port name
- **有川** (32.9870097, 129.1112603), 0 sailings: OSM/Nominatim display does not clearly overlap the port name
- **桜島** (31.592602, 130.6000526), 0 sailings: OSM/Nominatim display does not clearly overlap the port name
- **興居島（由良** (34.4715466, 135.8277994), 0 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name
- **西ノ島** (33.6024253, 130.271485), 0 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name; generic same-name port is not manually verified
- **野崎** (33.1887685, 129.1389463), 0 sailings: weak geocoder source still marked needs_precise_port_review; OSM/Nominatim display does not clearly overlap the port name

## Watch

- **佐久島西港**, 28 sailings: rail is nearby at 7538m; confirm this is truly an island/no-access case; bus stop is nearby at 7417m but outside 2km
- **似島港**, 26 sailings: rail is nearby at 5404m; confirm this is truly an island/no-access case; bus stop is nearby at 4108m but outside 2km
- **寒風沢港**, 26 sailings: rail is nearby at 5449m; confirm this is truly an island/no-access case; bus stop is nearby at 7047m but outside 2km
- **桂島港**, 26 sailings: rail is nearby at 5189m; confirm this is truly an island/no-access case; bus stop is nearby at 4622m but outside 2km
- **石浜港**, 26 sailings: rail is nearby at 4133m; confirm this is truly an island/no-access case; bus stop is nearby at 6928m but outside 2km
- **野々島港**, 26 sailings: rail is nearby at 4721m; confirm this is truly an island/no-access case; bus stop is nearby at 5813m but outside 2km
- **初島港**, 20 sailings: rail is nearby at 8203m; confirm this is truly an island/no-access case
- **御所浦**, 20 sailings: bus stop is nearby at 5648m but outside 2km
- **沼島港**, 20 sailings: bus stop is nearby at 3780m but outside 2km
- **網地港**, 16 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **佐久島東港**, 14 sailings: rail is nearby at 7843m; confirm this is truly an island/no-access case; bus stop is nearby at 8540m but outside 2km
- **利島港**, 14 sailings: multiple operator contexts: 東海汽船, 神新汽船; both nearest rail and bus are far; coordinate may still need map spot-check
- **宗像大島港**, 14 sailings: bus stop is nearby at 7592m but outside 2km
- **大多府港**, 13 sailings: rail is nearby at 8309m; confirm this is truly an island/no-access case; bus stop is nearby at 4677m but outside 2km
- **朴島港**, 13 sailings: rail is nearby at 5758m; confirm this is truly an island/no-access case; bus stop is nearby at 8290m but outside 2km
- **周防大島久賀港**, 12 sailings: rail is nearby at 8369m; confirm this is truly an island/no-access case; bus stop is nearby at 8677m but outside 2km
- **式根島野伏港**, 12 sailings: multiple operator contexts: 東海汽船, 神新汽船
- **新島港**, 12 sailings: multiple operator contexts: 東海汽船, 神新汽船
- **男木**, 12 sailings: rail is nearby at 7831m; confirm this is truly an island/no-access case; bus stop is nearby at 5920m but outside 2km
- **走島港**, 12 sailings: bus stop is nearby at 4443m but outside 2km
- **保戸島**, 10 sailings: rail is nearby at 8985m; confirm this is truly an island/no-access case
- **印通寺**, 10 sailings: bus stop is nearby at 2897m but outside 2km
- **竹富港**, 10 sailings: bus stop is nearby at 7177m but outside 2km
- **阿多田港**, 10 sailings: rail is nearby at 5178m; confirm this is truly an island/no-access case; bus stop is nearby at 3549m but outside 2km
- **五島久賀港**, 8 sailings: bus stop is nearby at 9463m but outside 2km
- **佐柳**, 8 sailings: bus stop is nearby at 9401m but outside 2km
- **六連島**, 8 sailings: rail is nearby at 5502m; confirm this is truly an island/no-access case; bus stop is nearby at 5829m but outside 2km
- **壱岐大島港**, 8 sailings: bus stop is nearby at 6525m but outside 2km
- **大津島馬島港**, 8 sailings: rail is nearby at 7982m; confirm this is truly an island/no-access case
- **糸島姫島港**, 8 sailings: rail is nearby at 8155m; confirm this is truly an island/no-access case
- **西表上原港**, 8 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **八幡浜大島港**, 6 sailings: rail is nearby at 6790m; confirm this is truly an island/no-access case; bus stop is nearby at 6790m but outside 2km
- **六島**, 6 sailings: bus stop is nearby at 6711m but outside 2km
- **度島**, 6 sailings: rail is nearby at 6826m; confirm this is truly an island/no-access case
- **母島沖港**, 6 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **波照間港**, 6 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **西表大原港**, 6 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **見島本村港**, 6 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **八丈島底土港**, 5 sailings: multiple operator contexts: 伊豆諸島開発, 東海汽船; bus stop is nearby at 3216m but outside 2km
- **祝島港**, 5 sailings: bus stop is nearby at 9382m but outside 2km
- **安居島**, 4 sailings: rail is nearby at 2017m; confirm this is truly an island/no-access case; bus stop is nearby at 9215m but outside 2km
- **座間味港**, 4 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **渡名喜港**, 4 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **鳩間港**, 4 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **青ヶ島三宝港**, 3 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **兼城港**, 2 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **友住**, 2 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **渡嘉敷港**, 2 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **粟国港**, 2 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
- **舳倉島港**, 2 sailings: both nearest rail and bus are far; coordinate may still need map spot-check
