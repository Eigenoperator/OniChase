# STATUS

## Current Focus
继续收新的主 `v2` 联机试玩稳定性，同时推进 `v3` 第一阶段的真实东京线网与真实车次数据底座。
## Done
- 已补写 `diary/DIARY-2026-04-06.md` 与 `diary/DIARY-2026-04-07.md`，并创建 `memory/MEMORY-2026-04-07.md`、`memory/MEMORY-2026-04-08.md` 作为对应 raw memory。
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座与多源官方 train-detail 抓取链：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本、`JR East / JR West / JR Kyushu` 官方时刻表入口。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1139` 趟 weekday 真实新干线列车实例。
- 已打通 `JR Central` 的 `station-guide -> ResultControl -> tokainr.cgi` 官方链，并新增 `data/shinkansen_v2_jrcentral_tokaido_weekday_supplement.json`，补入 `43` 趟东海道中途始发/短折返真实班次。
- 已修正 `JR Kyushu / Nishi-Kyushu` 双栏 `Kamome` 详情页解析错误，`Takeo-Onsen -> Nagasaki` 与 `Nagasaki -> Takeo-Onsen` 现在都能正确进入全国合并库。
- 已修正全国合并逻辑，跨运营商同一趟真实列车现在会按真实服务名/号合并，不再把 `JR Central` 的东海道补丁短版和 `JR West / JR East` 的全程版重复算两趟；重新收敛后全国 weekday 数据稳定为 `1139` 趟。
- 已开始 `v2` 游戏层：新增 `data/shinkansen_v2_bundle.json` 和第一版 `app/v2_local_client.py`，现在可以在全国新干线图上点站、浏览真实发车，并把列车段接进 plan board。
- 已把 `v2` 本地端和网页端都推进到“选车后选目标站”，并补上 `runner / hunter`、phase 时钟、`Start Game`、live 地图位置、`06:00 -> 18:00` 时间窗、每过 `1` 小时自动重新进入 `PLANNING`，以及中途重进 `PLANNING` 时按“当前时刻位置”继续规划而不是误跳到整条计划终点。
- 已继续把 `v2` 网页端往本地端收齐：补上 `Run Simulation`、结果摘要、replay 事件列表、事件详情，以及地图随选中事件跳到对应状态。
- 已把 `v2` 网页端地图改成可缩放/拖拽，并按缩放级别动态显示站名；页面也已收成“先进独立大厅、再进固定视口主游戏页”的结构，原来把顶栏挤爆的房间控件已从游戏主界面拆出，公开大厅不再直接暴露 `room server URL`，并已接入公网 Render 房间服务器默认配置。
- 已继续修正 `v2` 网页端地图交互：站点圆点现在会随缩放更合理地缩放，放大后不会显得过大，同时拖拽边界已改成按真实地图内容范围动态计算。
- 已修正 `v2` 固定页面后的右栏交互问题：右侧面板恢复为整栏可滚动，同时保留内部列表滚动，不再因为固定高度而把下半部分裁死。
- 已把 `v2` 网页端的右侧 planning 交互切换为和 `v1` 同一条主流程：统一的 `Planning Actions` + `Train Outlook`，支持 `选车 -> 选目标站`，并让地图点击与右侧动作区共用同一套逻辑。
- 已继续收 `v2` 网页地图观感：缩小默认站名字号，并在选中一趟车后把后续停站直接高亮在地图上，方便不看右侧也能判断路线。
- 已修正 `v2` 抓捕边界：同分钟里若是一人下车到站、另一人从同站上不同列车离开，则不再误判 `same_node`；回归确认 `same_node`、`same_train` 和“异车交错未抓”三类判定都成立。
- 已启动并打通 `v2` 多人联机底座：新增 `ONLINE_ARCHITECTURE.md`、`ONLINE_PROTOCOL.md`、`scripts/engine/v2_online_room_server.py` 和 `START_ONICHASE_V2_SERVER.sh`，网页端也已接上建房/入房/submit plan/ready；当前联机版已补上 seat token / seat lock，并确认 `create room -> join runner/hunter -> submit plan -> ready/start -> LIVE 推进 -> authoritative capture` 全部跑通，同时已补 `render.yaml`、`ONLINE_DEPLOYMENT.md` 和 `docs/data/v2_online_config.json` 作为公网部署入口。
- 已完成 `v3` 第一版 GIS Shinkansen pilot：包括架构/Schema、`V3_PILOT_BUNDLE_PLAN.md`、`data/v3_shinkansen_bundle.json`、`visuals/v3_shinkansen_multiscale_map.svg`、`ui/v3_web_client.html`、`docs/v3.html`、`data/v3_gis/*.geojson`、`docs/data/v3_tiles/` tile-ready GeoJSON 金字塔、地图 + route timetable diagram 的同源联动，以及开始直接消费 `v3_tiles` 的 tile-driven 地图层。
- 已根据 `UI_BRIEF_V2.md` 试做过一轮更激进的主 `v2` UI 重构；当前已按反馈把网页壳层退回到重做前的稳定布局与浅色配色，保留玩法和联机逻辑不变。
- 已完成版本迁移：原 `v3` GIS-first 新干线玩法页已提升为新的主 `v2`；公开网站现只保留 `v1` 和主 `v2`，不再公开 `v2-legacy` 与 `v3` 页面。
- 已继续收 `v2` 多人体验：大厅里新增了可复制的房间号显示，主游戏页新增轻量 `Room` 区来承载复制房间号、`Submit Plan`、`Ready`、返回大厅等关键联机动作，同时把对手是否已加入、是否 ready 的状态压进大厅状态文案、房间状态卡和顶部时间条。
- 已完成 `v3` 统一 train index 第一版：新增 `scripts/ingest/build_v3_train_index.py`，把 `JR East / Tokyo Metro / Toei / Keio / Tokyu / Seibu / Keisei / Keikyu / Odakyu / Tobu / Rinkai / Yurikamome / Tokyo Monorail / Tama Monorail / Tsukuba Express / Shinkansen` 统一登记到 `data/v3_train_manifest.json`，当前共 `39450` 趟真实列车、`1415` 个 station departure key。
- 已完成 `v3` 统一 train schema 与 station departure lookup：生成 `data/v3_trains_unified.json.gz` 和 `data/v3_station_departures.json.gz`，统一字段为 `operator / line / train_number / service_name / direction / stops / source / service_day`，并补上 JR 英文站名到日文地图站名的 alias join。
- 已把 `v3` 网页重新接上真实 map + timetable 同源联动：`ui/v3_tokyo_phase1_map.html` 和 `docs/v3.html` 现在可显示真实线路和站名，点击站点显示真实 departure board，选择列车后显示停站列表并高亮停站/线路；已用 Playwright headless 验证点击东京可显示 `4221` 条真实发车并选中一班列车。
- 已按新决策把 `v3` 交互层切换为复用主 `v2` UI 代码：新增 `scripts/ingest/build_v3_tokyo_v2_bundle.py` 生成 `data/v3_tokyo_bundle.json`，让 `docs/v3.html` 从 `ui/v2_web_client.html` 派生并只注入 v3 数据 URL；当前 v3 bundle 有 `1529` 个真实坐标站点、`302` 条 service route、`4147` 条 track centerline、`39318` 趟可进入 v2 planning flow 的列车。
- 已把复用 `v2` UI 的 `v3` 发布到 GitHub Pages：`https://eigenoperator.github.io/OniChase/v3.html` 当前线上可加载 `77,940,421` bytes 的 `v3_tokyo_bundle.json`，公开 URL Playwright smoke test 已确认点击东京站后能看到真实发车、选择列车并显示后续停站。
## In Progress
- 正在继续把新的主 `v2` 收成稳定版本：一方面保留 GIS-first 地图/diagram 联动，另一方面把联机页面细节、单机页面体验和新的 UI brief 继续对齐。
- 已把公开 `v2` 网页的多人配置接到 Render 房间服务器 `https://onichase.onrender.com`，现在公开网页会默认尝试连公网联机后端。
- 正在继续查 `v2` 是否还缺明显的短折返 / 中途始发终到班次，但目前已没有新的阻塞级问题。
- `v3` 当前进入 map + timetable 同源联动稳定化阶段：先继续收 station identity / line matching / dense map click 体验，再迁移 `v2` 追逃规划逻辑。
## Blockers
- 当前仓库和本会话里没有可用的 Notion 工具、脚本或配置，所以无法直接完成真正的 Notion 更新。
- `JR Central` 仍没有像 `JR East / JR West` 那样直接暴露单趟 train-detail 页，所以后面若要进一步精细化，仍需继续完善“按全站 departure grid 聚合 train instances”的逻辑。
## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-04-03] 不再为每个小改动都 commit / push；只在显著变化时同步，但有实质工作的一天仍需至少同步一次。
- [2026-04-03] 产品路线现已收敛为 `v1 山手线`、`v2 新干线全图可玩版`、`v3 新干线 GIS 升级版`。
- [2026-04-04] `v2` 使用全图所有真实新干线列车，并保留真实列车名，例如 `Nozomi 1`、`Kagayaki 503`。
- [2026-04-05] `JR Kyushu` 双栏列车详情页必须按目标服务列解析，不能把 `Relay Kamome` 误当作 `Nishi-Kyushu Kamome`。
- [2026-04-05] 全国合并默认优先按真实 `service_name + service_number (+ direction)` 识别同一趟列车，而不是只按各运营商自带的 `train_number`。
- [2026-04-07] GIS-first 新干线页面已成为新的主 `v2`；公开网站现在只保留 `v1` 与主 `v2`，`v3` 暂不定义。
- [2026-04-13] `v3 phase 1` 先做“东京周边真实地图 + 真实车次数据”，并且保持所有站点真实位置，不通过伪造站位解决高密显示问题。
- [2026-04-19] `v3` 所有 UI 交互复用主 `v2` 代码；`v3` 只维护 v2-compatible 数据适配层和东京真实数据，不再维护一套独立交互页面。

## Next
1. 继续收主 `v2` 联机页面细节，例如房间状态、ready / planning / live 同步，以及单人/多人一致性。
2. 继续收 `v3_tokyo_bundle.json` 的 station-group / line-route 映射质量，尤其是同名多站、密集中心区点击命中、route card 数量和 train line_id 到物理线路名的映射。
3. 在 v2 UI 复用路径上继续验证 `v3` 的 planning / live / capture / replay，而不是维护独立 v3 UI。
