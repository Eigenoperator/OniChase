# STATUS

## Current Focus
把 `v1` 山手线试玩底座保持稳定，继续收 `v2` 全国新干线可玩壳，并正式启动 `v3` 东京 GIS 底座架构设计。

## Done
- 已把 GitHub Pages 主页拆成版本入口页：`docs/index.html` 现在单独列出 `v1` 山手线与 `v2` 全国新干线两个可玩入口。
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本。
- 已完成 `v2` 官方时刻表入口清单与站点清单，接通 `JR East / JR West / JR Kyushu` 多源 train-detail 抓取链。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1139` 趟 weekday 真实新干线列车实例。
- 已新增 `visuals/shinkansen_v2_weekday_timetable.svg`，按线路分 panel 可视化 `v2` 全国新干线 weekday 时刻图。
- 已打通 `JR Central` 的 `station-guide -> ResultControl -> tokainr.cgi` 官方链，并新增 `data/shinkansen_v2_jrcentral_tokaido_weekday_supplement.json`，补入 `43` 趟东海道中途始发/短折返真实班次。
- 已修正 `JR Kyushu / Nishi-Kyushu` 双栏 `Kamome` 详情页解析错误，`Takeo-Onsen -> Nagasaki` 与 `Nagasaki -> Takeo-Onsen` 现在都能正确进入全国合并库。
- 已修正全国合并逻辑，跨运营商同一趟真实列车现在会按真实服务名/号合并，不再把 `JR Central` 的东海道补丁短版和 `JR West / JR East` 的全程版重复算两趟；重新收敛后全国 weekday 数据稳定为 `1139` 趟。
- 已开始 `v2` 游戏层：新增 `data/shinkansen_v2_bundle.json` 和第一版 `app/v2_local_client.py`，现在可以在全国新干线图上点站、浏览真实发车，并把列车段接进 plan board。
- 已把 `v2` 本地端和网页端都推进到“选车后选目标站”：不再默认坐到终点站，而是先选一趟真实列车，再从后续停站中选一个目标站接进 plan board。
- 已把 `v2` 本地端推进到接近 `v1` 的 phase 效果：补上 `runner / hunter` 模式、`PLANNING / LIVE / ENDED`、`Start Game`、live 地图位置、抓捕结束反馈、模拟结果和 replay 事件列表。
- 已把 `v2` 网页端推进到同一条主玩法流：补上 `runner / hunter` 模式、phase 时钟、`Start Game`、live 地图位置和基于 plan steps 的全国新干线规划。
- 已继续把 `v2` 网页端往本地端收齐：补上 `Run Simulation`、结果摘要、replay 事件列表、事件详情，以及地图随选中事件跳到对应状态。
- 已把 `v2` 右侧列车显示统一为英文服务名优先，例如 `Nozomi 1`、`Kagayaki 503`，不再在右栏直接显示日文车名。
- 已把 `v2` 网页端地图改成可缩放/拖拽，并按缩放级别动态显示站名；同时页面改成固定视口布局，主要模块内部可独立滚动，减少整页空白和长页面滚动。
- 已继续修正 `v2` 网页端地图交互：站点圆点现在会随缩放更合理地缩放，放大后不会显得过大，同时拖拽边界已改成按真实地图内容范围动态计算。
- 已修正 `v2` 固定页面后的右栏交互问题：右侧面板恢复为整栏可滚动，同时保留内部列表滚动，不再因为固定高度而把下半部分裁死。
- 已更新 `README.md`，把 GitHub Pages 首页、`v1` 页面、`v2` 页面三个公开地址都写清楚。
- 已把 `v2` 网页端的右侧 planning 交互切换为和 `v1` 同一条主流程：统一的 `Planning Actions` + `Train Outlook`，支持 `选车 -> 选目标站`，并让地图点击与右侧动作区共用同一套逻辑。
- 已继续收 `v2` 网页地图观感：缩小默认站名字号，并在选中一趟车后把后续停站直接高亮在地图上，方便不看右侧也能判断路线。
- 已新增 `V3_GIS_ARCHITECTURE.md` 和 `V3_GIS_SCHEMA.md`，正式定义 `v3` 的物理网络层、运营服务层、游戏抽象层以及 OniChase 自己的 canonical transit bundle。

## In Progress
- 正在同时推进 `v2` 和 `v3`：`v2` 继续收本地端与网页端的一致性、 多段规划和结果反馈，`v3` 先锁 GIS 架构与中间层 schema，再决定第一个东京 pilot 区域。
- 正在继续查 `v2` 是否还缺明显的短折返 / 中途始发终到班次，但目前已没有新的阻塞级问题。

## Blockers
- 当前仓库和本会话里没有可用的 Notion 工具、脚本或配置，所以无法直接完成真正的 Notion 更新。
- `JR Central` 仍没有像 `JR East / JR West` 那样直接暴露单趟 train-detail 页，所以后面若要进一步精细化，仍需继续完善“按全站 departure grid 聚合 train instances”的逻辑。

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-04-03] 不再为每个小改动都 commit / push；只在显著变化时同步，但有实质工作的一天仍需至少同步一次。
- [2026-04-03] 产品路线固定为 `v1 山手线`、`v2 新干线全图`、`v3 东京全图`。
- [2026-04-04] `v2` 使用全图所有真实新干线列车，并保留真实列车名，例如 `Nozomi 1`、`Kagayaki 503`。
- [2026-04-05] `JR Kyushu` 双栏列车详情页必须按目标服务列解析，不能把 `Relay Kamome` 误当作 `Nishi-Kyushu Kamome`。
- [2026-04-05] 全国合并默认优先按真实 `service_name + service_number (+ direction)` 识别同一趟列车，而不是只按各运营商自带的 `train_number`。

## Next
1. 继续实测 `v2` 网页端新 action flow 和地图高亮，确认它已经能像 `v1` 一样稳定完成 `选车 -> 选站 -> 接续下一段`。
2. 为 `v3` 选定第一个东京 GIS pilot 区域，并开始定义最小 `V3TransitBundle`。
3. 在 `v2` 游戏壳稳定后，再继续逐线补 anomaly checklist 的余项。
