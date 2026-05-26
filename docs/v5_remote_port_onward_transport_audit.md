# V5 Remote Port Onward Transport Audit

This audit applies the gameplay rule that true terminal-only remote ports do
not need bus collection.  It does not collect bus data.  It decides what to
review first.

## Summary

- `remotePortCount`: 111
- `identityReviewFirst`: 36
- `type2NoCollectionNeededNow`: 0
- `type2ConfirmedNoOnwardCollection`: 6
- `type2CandidateConfirmNoOnwardCollection`: 0
- `type1CollectIslandBus`: 69

## identity_review_first

- **黒島** (32 sailings): port identity or coordinate is not trusted enough for onward triage
- **宗方港** (22 sailings): port identity or coordinate is not trusted enough for onward triage
- **古仁屋** (21 sailings): port identity or coordinate is not trusted enough for onward triage
- **佐合島** (20 sailings): port identity or coordinate is not trusted enough for onward triage
- **神浦** (19 sailings): port identity or coordinate is not trusted enough for onward triage
- **島浦** (16 sailings): port identity or coordinate is not trusted enough for onward triage
- **細島港** (16 sailings): port identity or coordinate is not trusted enough for onward triage
- **湊** (14 sailings): port identity or coordinate is not trusted enough for onward triage
- **玄界島** (14 sailings): port identity or coordinate is not trusted enough for onward triage
- **伊保田港** (12 sailings): port identity or coordinate is not trusted enough for onward triage
- **出羽島** (12 sailings): port identity or coordinate is not trusted enough for onward triage
- **相島** (12 sailings): port identity or coordinate is not trusted enough for onward triage
- **馬島** (12 sailings): port identity or coordinate is not trusted enough for onward triage
- **家浦** (10 sailings): port identity or coordinate is not trusted enough for onward triage
- **岡村港** (10 sailings): port identity or coordinate is not trusted enough for onward triage
- **牛島** (10 sailings): port identity or coordinate is not trusted enough for onward triage
- **伊保田** (8 sailings): port identity or coordinate is not trusted enough for onward triage
- **口永良部島港** (8 sailings): port identity or coordinate is not trusted enough for onward triage
- **情島** (8 sailings): port identity or coordinate is not trusted enough for onward triage
- **与路** (7 sailings): port identity or coordinate is not trusted enough for onward triage
- **嵯峨島** (6 sailings): port identity or coordinate is not trusted enough for onward triage
- **斎島** (6 sailings): port identity or coordinate is not trusted enough for onward triage
- **藍島** (6 sailings): port identity or coordinate is not trusted enough for onward triage
- **貝津** (6 sailings): port identity or coordinate is not trusted enough for onward triage
- **島間港** (4 sailings): port identity or coordinate is not trusted enough for onward triage
- **片島** (4 sailings): port identity or coordinate is not trusted enough for onward triage
- **青島** (4 sailings): port identity or coordinate is not trusted enough for onward triage
- **黄島** (4 sailings): port identity or coordinate is not trusted enough for onward triage
- **小呂島** (2 sailings): port identity or coordinate is not trusted enough for onward triage
- **中島** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **嘉島** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **有川** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **桜島** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **興居島（由良** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **西ノ島** (0 sailings): port identity or coordinate is not trusted enough for onward triage
- **野崎** (0 sailings): port identity or coordinate is not trusted enough for onward triage

## type2_no_collection_needed_now

- None.

## type2_confirmed_no_onward_collection

- **小値賀大島港** (8 sailings): official town transport page lists ferry access to Oshima, but land bus coverage only for Ojika main island; no Oshima public bus source found
- **見島本村港** (6 sailings): official/tourism access pages show ship access and mainland access, but no public island bus source was found for Mishima
- **青ヶ島三宝港** (3 sailings): official barrier-free terminal record says Aogashima has no bus, taxi, or other land public transport
- **硫黄島港** (2 sailings): official Mishima village transport plan says the village has no bus/taxi public transport
- **舳倉島港** (2 sailings): official/search review found mainland Wajima bus but no public bus source on Hegurajima; treat as terminal-only until an island transport source appears
- **飛島勝浦港** (2 sailings): island profile says Tobishima has no taxi or transport service and movement is on foot or free rental bicycle

## type2_candidate_confirm_no_onward_collection

- None.

## type1_collect_island_bus

- **佐久島西港** (28 sailings): bus source exists within 7417m but outside 2km; likely needs local access review
- **似島港** (26 sailings): bus source exists within 4108m but outside 2km; likely needs local access review
- **寒風沢港** (26 sailings): bus source exists within 7047m but outside 2km; likely needs local access review
- **桂島港** (26 sailings): bus source exists within 4622m but outside 2km; likely needs local access review
- **石浜港** (26 sailings): bus source exists within 6928m but outside 2km; likely needs local access review
- **野々島港** (26 sailings): bus source exists within 5813m but outside 2km; likely needs local access review
- **大分姫島港** (24 sailings): remote record, but nearby access signal is ambiguous
- **初島港** (20 sailings): rail exists within 8203m but outside 2km; likely needs local access review
- **御所浦** (20 sailings): bus source exists within 5648m but outside 2km; likely needs local access review
- **沼島港** (20 sailings): bus source exists within 3780m but outside 2km; likely needs local access review
- **網地港** (16 sailings): official Ishinomaki source says Ajishima has a citizen bus; collect the Ajishima bus system
- **佐久島東港** (14 sailings): bus source exists within 8540m but outside 2km; likely needs local access review
- **利島港** (14 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **大島岡田港** (14 sailings): official Oshima Bus source lists route bus service at/around Okada Port; collect Oshima bus
- **宗像大島港** (14 sailings): bus source exists within 7592m but outside 2km; likely needs local access review
- **田代島仁斗田港** (14 sailings): remote record, but nearby access signal is ambiguous
- **大多府港** (13 sailings): bus source exists within 4677m but outside 2km; likely needs local access review
- **朴島港** (13 sailings): bus source exists within 8290m but outside 2km; likely needs local access review
- **周防大島久賀港** (12 sailings): bus source exists within 8677m but outside 2km; likely needs local access review
- **式根島野伏港** (12 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **新島港** (12 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **男木** (12 sailings): bus source exists within 5920m but outside 2km; likely needs local access review
- **走島港** (12 sailings): bus source exists within 4443m but outside 2km; likely needs local access review
- **飛島** (12 sailings): remote record, but nearby access signal is ambiguous
- **保戸島** (10 sailings): rail exists within 8985m but outside 2km; likely needs local access review
- **印通寺** (10 sailings): bus source exists within 2897m but outside 2km; likely needs local access review
- **小値賀柳港** (10 sailings): official Ojika/Kyushu passenger-ship sources list Ojika Kotsu access to Yanagi; collect Ojika demand bus
- **的山港** (10 sailings): remote record, but nearby access signal is ambiguous
- **竹富港** (10 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **阿多田港** (10 sailings): bus source exists within 3549m but outside 2km; likely needs local access review
- **五島久賀港** (8 sailings): bus source exists within 9463m but outside 2km; likely needs local access review
- **佐柳** (8 sailings): bus source exists within 9401m but outside 2km; likely needs local access review
- **六連島** (8 sailings): bus source exists within 5829m but outside 2km; likely needs local access review
- **壱岐大島港** (8 sailings): bus source exists within 6525m but outside 2km; likely needs local access review
- **大津島馬島港** (8 sailings): rail exists within 7982m but outside 2km; likely needs local access review
- **瀬相** (8 sailings): official tourism source says Kakeroma buses wait at Sesou Port; collect Kakeroma Bus
- **笛吹** (8 sailings): official Ojika/Kyushu passenger-ship sources list Ojika Kotsu access to Fuefuki; collect Ojika demand bus
- **糸島姫島港** (8 sailings): rail exists within 8155m but outside 2km; likely needs local access review
- **西表上原港** (8 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **鮎川港** (8 sailings): remote record, but nearby access signal is ambiguous
- **神島港** (7 sailings): remote record, but nearby access signal is ambiguous
- **上五島** (6 sailings): official Shinkamigoto source says the town has public route buses; collect Shinkamigoto/Saihi bus
- **八幡浜大島港** (6 sailings): bus source exists within 6790m but outside 2km; likely needs local access review
- **六島** (6 sailings): bus source exists within 6711m but outside 2km; likely needs local access review
- **小浜港** (6 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **度島** (6 sailings): rail exists within 6826m but outside 2km; likely needs local access review
- **柱島港** (6 sailings): remote record, but nearby access signal is ambiguous
- **椛島** (6 sailings): remote record, but nearby access signal is ambiguous
- **母島沖港** (6 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **江島港** (6 sailings): remote record, but nearby access signal is ambiguous
- **波照間港** (6 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **生間** (6 sailings): official tourism source says Kakeroma buses wait at Ikenma Port; collect Kakeroma Bus
- **西表大原港** (6 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **黒島港** (6 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **八丈島底土港** (5 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **祝島港** (5 sailings): bus source exists within 9382m but outside 2km; likely needs local access review
- **安居島** (4 sailings): bus source exists within 9215m but outside 2km; likely needs local access review
- **座間味港** (4 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **渡名喜港** (4 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **粟島港** (4 sailings): remote record, but nearby access signal is ambiguous
- **郷ノ首** (4 sailings): remote record, but nearby access signal is ambiguous
- **鳩間港** (4 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **佐世保柳港** (3 sailings): official passenger-ship source lists Ojika Kotsu at Yanagi; collect Ojika demand bus
- **兼城港** (2 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **友住** (2 sailings): official Shinkamigoto source and current bus references show Saihi Bus service through Tomozumi; collect Shinkamigoto/Saihi bus
- **渡嘉敷港** (2 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **粟国港** (2 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
- **輪島港** (2 sailings): remote record, but nearby access signal is ambiguous
- **阿嘉港** (2 sailings): island/bus hint exists; collect or verify official island bus before terminal-only decision
