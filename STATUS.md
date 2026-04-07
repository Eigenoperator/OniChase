# STATUS

## Current Focus
保持 `v1` 稳定，并把 GIS-first 新干线主玩法正式收敛为新的 `v2`；公开入口只保留 `v1` 和 `v2`。

## Done
- 已补写 `diary/DIARY-2026-04-06.md`，并创建 `memory/MEMORY-2026-04-07.md` 作为今天的 raw memory。
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座与多源官方 train-detail 抓取链：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本、`JR East / JR West / JR Kyushu` 官方时刻表入口。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1139` 趟 weekday 真实新干线列车实例。
- 已打通 `JR Central` 的 `station-guide -> ResultControl -> tokainr.cgi` 官方链，并新增 `data/shinkansen_v2_jrcentral_tokaido_weekday_supplement.json`，补入 `43` 趟东海道中途始发/短折返真实班次。
- 已修正 `JR Kyushu / Nishi-Kyushu` 双栏 `Kamome` 详情页解析错误，`Takeo-Onsen -> Nagasaki` 与 `Nagasaki -> Takeo-Onsen` 现在都能正确进入全国合并库。
- 已修正全国合并逻辑，跨运营商同一趟真实列车现在会按真实服务名/号合并，不再把 `JR Central` 的东海道补丁短版和 `JR West / JR East` 的全程版重复算两趟；重新收敛后全国 weekday 数据稳定为 `1139` 趟。
- 已开始 `v2` 游戏层：新增 `data/shinkansen_v2_bundle.json` 和第一版 `app/v2_local_client.py`，现在可以在全国新干线图上点站、浏览真实发车，并把列车段接进 plan board。
- 已把 `v2` 本地端和网页端都推进到“选车后选目标站”，并补上 `runner / hunter`、phase 时钟、`Start Game`、live 地图位置、`06:00 -> 18:00` 时间窗，以及每过 `1` 小时自动重新进入 `PLANNING` 的全国新干线规划。
- 已继续把 `v2` 网页端往本地端收齐：补上 `Run Simulation`、结果摘要、replay 事件列表、事件详情，以及地图随选中事件跳到对应状态。
- 已把 `v2` 网页端地图改成可缩放/拖拽，并按缩放级别动态显示站名；同时页面改成固定视口布局，主要模块内部可独立滚动，减少整页空白和长页面滚动。
- 已继续修正 `v2` 网页端地图交互：站点圆点现在会随缩放更合理地缩放，放大后不会显得过大，同时拖拽边界已改成按真实地图内容范围动态计算。
- 已修正 `v2` 固定页面后的右栏交互问题：右侧面板恢复为整栏可滚动，同时保留内部列表滚动，不再因为固定高度而把下半部分裁死。
- 已把 `v2` 网页端的右侧 planning 交互切换为和 `v1` 同一条主流程：统一的 `Planning Actions` + `Train Outlook`，支持 `选车 -> 选目标站`，并让地图点击与右侧动作区共用同一套逻辑。
- 已继续收 `v2` 网页地图观感：缩小默认站名字号，并在选中一趟车后把后续停站直接高亮在地图上，方便不看右侧也能判断路线。
- 已把 `v3` 的线路联动思路合并进 `v2` 网页端：新增 `ROUTE FOCUS` 面板、线路卡片、地图线条点击高亮、选中线路停靠站高亮，以及路线级别的标签增强。
- 已修正 `v2 / v3` 网页地图缩放时的站名可读性：站名字号和描边现在会随缩放反向调节，且高 zoom 时的标签密度也更克制，不会一放大就整片重叠。
- 已完成 `v3` 第一版 GIS Shinkansen pilot：包括架构/Schema、`V3_PILOT_BUNDLE_PLAN.md`、`data/v3_shinkansen_bundle.json`、`visuals/v3_shinkansen_multiscale_map.svg`、`ui/v3_web_client.html`、`docs/v3.html`、`data/v3_gis/*.geojson`、`docs/data/v3_tiles/` tile-ready GeoJSON 金字塔、地图 + route timetable diagram 的同源联动，以及开始直接消费 `v3_tiles` 的 tile-driven 地图层。
- 已继续推进 `v3` 地图/diagram 联动：diagram hover 现可同步高亮地图上的具体 trip 路径；点选站点时，右栏会额外显示“当前选中线路在该站的真实发车集合”。
- 已把 `v1` 的核心游戏逻辑接入 `v3` 网页端：补上 `runner / hunter` 模式、`PLANNING / LIVE / ENDED`、`Load Test Preset`、`Start Game`、`Run Simulation`、plan board、实时地图玩家位置和 `same_node / same_train` 抓捕。
- 已完成版本迁移：原 `v3` GIS-first 新干线玩法页已提升为新的主 `v2`；公开网站现只保留 `v1` 和主 `v2`，不再公开 `v2-legacy` 与 `v3` 页面。

## In Progress
- 正在继续把新的主 `v2` 收成稳定版本：一方面保留 GIS-first 地图/diagram 联动，另一方面把原来 `v1` 的可玩逻辑继续在全国新干线上收顺。
- 正在继续查 `v2` 是否还缺明显的短折返 / 中途始发终到班次，但目前已没有新的阻塞级问题。

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

## Next
1. 继续实测新的主 `v2`，确认地图、diagram、plan board、capture、replay 这一整套在全国新干线上稳定工作。
2. 持续收主 `v2` 的地图视觉和交互细节，避免 GIS 表达比旧版更强但玩法上更难用。
3. 在主 `v2` 稳定后，再继续逐线补 anomaly checklist 的余项。
