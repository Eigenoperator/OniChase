# STATUS

## Current Focus
把 `v1` 山手线试玩底座保持稳定，同时把 `v2` 全国新干线真实列车数据接成可继续扩充的 train-instance 管线。

## Done
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本。
- 已完成 `v2` 官方时刻表入口清单与站点清单，接通 `JR East / JR West / JR Kyushu` 多源 train-detail 抓取链。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1119` 趟 weekday 真实新干线列车实例。
- 已补上 `Joetsu` 的 `Niigata -> Tokyo` 上行，以及 `Hokuriku` 的 `Nagano` 上下行和 `Tsuruga -> Tokyo` 上行。
- 已新增 `visuals/shinkansen_v2_weekday_timetable.svg`，按线路分 panel 可视化 `v2` 全国新干线 weekday 时刻图。

## In Progress
- 正在继续查 `v2` 是否还缺明显的短折返 / 中途始发终到班次，尤其是 `Tokaido / Sanyo / Hokuriku / Joetsu`。
- 正在把 `v2` 的 source inventory 和 station timetable inventory 收成长期可复用的 ingestion 底座。

## Blockers
- 当前仓库和本会话里没有可用的 Notion 工具、脚本或配置，所以无法直接完成真正的 Notion 更新。
- `JR Central` 官方入口仍需继续核对；`Tokaido` 全量列车覆盖目前主要来自 `Tokyo` 与 `Shin-Osaka` 侧入口，可能还缺部分中途始发/终到短折返。

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-04-03] 不再为每个小改动都 commit / push；只在显著变化时同步，但有实质工作的一天仍需至少同步一次。
- [2026-04-03] 产品路线固定为 `v1 山手线`、`v2 新干线全图`、`v3 东京全图`。
- [2026-04-04] `v2` 使用全图所有真实新干线列车，并保留真实列车名，例如 `Nozomi 1`、`Kagayaki 503`。

## Next
1. 继续补 `v2` 尚未覆盖的关键方向入口，优先查 `JR Central` 与可能缺失的短折返班次。
2. 把 `v2` 训练有素的 source inventory / station inventory 再收一轮，确保后续扩充不靠人工记忆。
3. 在 `v1` 维持稳定的前提下，开始规划 `v2` 的最小可玩模拟输入格式。
