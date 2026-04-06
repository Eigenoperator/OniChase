# STATUS

## Current Focus
把 `v1` 山手线试玩底座保持稳定，同时把 `v2` 全国新干线真实列车数据继续补齐并收成可靠的全国 train-instance 管线。

## Done
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本。
- 已完成 `v2` 官方时刻表入口清单与站点清单，接通 `JR East / JR West / JR Kyushu` 多源 train-detail 抓取链。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1139` 趟 weekday 真实新干线列车实例。
- 已补上 `Joetsu` 的 `Niigata -> Tokyo` 上行，以及 `Hokuriku` 的 `Nagano` 上下行和 `Tsuruga -> Tokyo` 上行。
- 已新增 `visuals/shinkansen_v2_weekday_timetable.svg`，按线路分 panel 可视化 `v2` 全国新干线 weekday 时刻图。
- 已打通 `JR Central` 的 `station-guide -> ResultControl -> tokainr.cgi` 官方链，并新增 `data/shinkansen_v2_jrcentral_tokaido_weekday_supplement.json`，补入 `43` 趟东海道中途始发/短折返真实班次。
- 已修正 `JR Kyushu / Nishi-Kyushu` 双栏 `Kamome` 详情页解析错误，`Takeo-Onsen -> Nagasaki` 与 `Nagasaki -> Takeo-Onsen` 现在都能正确进入全国合并库。
- 已修正全国合并逻辑，跨运营商同一趟真实列车现在会按真实服务名/号合并，不再把 `JR Central` 的东海道补丁短版和 `JR West / JR East` 的全程版重复算两趟；重新收敛后全国 weekday 数据稳定为 `1139` 趟。
- 已开始 `v2` 游戏层：新增 `data/shinkansen_v2_bundle.json` 和第一版 `app/v2_local_client.py`，现在可以在全国新干线图上点站、浏览真实发车，并把列车段接进 plan board。
- 已把第一版 `v2` 游戏壳同步到网页端：`docs/` 现在发布全国新干线版本，支持点站、浏览真实发车、查看后续停站并把车程加进 plan board。
- 已把 `v2` 本地端和网页端都推进到“选车后选目标站”：不再默认坐到终点站，而是先选一趟真实列车，再从后续停站中选一个目标站接进 plan board。
- 已把 `v2` 本地端推进到接近 `v1` 的 phase 效果：补上 `runner / hunter` 模式、`PLANNING / LIVE / ENDED`、`Start Game`、live 地图位置、抓捕结束反馈、模拟结果和 replay 事件列表。
- 已把 `v2` 网页端推进到同一条主玩法流：补上 `runner / hunter` 模式、phase 时钟、`Start Game`、live 地图位置和基于 plan steps 的全国新干线规划。
- 已完成 `2026-04-05` 的 diary 回补，并创建今天 `2026-04-06` 的 daily memory，保持日记与记忆链连续。

## In Progress
- 正在把 `v2` 从“最小可玩壳”继续推进到真正和 `v1` 等级接近的客户端，当前重点是继续压实本地端与网页端的一致性。
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
1. 继续收齐 `v2` 本地端和网页端之间仍然存在的细节差异，直到两边的 phase / planning / result 体验更接近 `v1`。
2. 让 `v2` 进入真正的多段规划状态，包括更顺的 plan board 编辑和后续 leg 继续接续。
3. 在 `v2` 游戏壳稳定后，再继续逐线补 anomaly checklist 的余项。
