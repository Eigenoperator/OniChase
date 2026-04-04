# STATUS
## Current Focus
把 `v1` 山手线试玩底座保持稳定，同时继续修正 `v2` 新干线全图草图。
## Done
- 已完成 `v1` 山手线真实站点、weekday 时刻表抓取、合并、可视化与第一版真实列车实例模拟器。
- 已完成本地客户端与网页端的 `PLANNING -> LIVE -> ENDED` 主流程、地图联动、`PLAN BOARD`、抓捕结束标记与抓捕说明卡。
- 已完成 hunter mode 第一轮开发：限制 hunter 视角信息、修正 hunter preset、补上 live 抓捕判定与结果反馈。
- 已完成一轮 `v1` 自测：真实山手线时刻表下 10 组代表性对局结果都符合预期。
- 已开始 `v2` 新干线全图草图，并已按真实网络关系修正 `Akita`、`Hokuriku`、`Kyushu / Nishi-Kyushu` 等关键错误。
- 已继续清理 `v2` 新干线图的可读性问题：去掉灰色辅助线路、拉开 `Joetsu` 与 `Hokuriku`、并把 `Yamagata` 与 `Akita` 调整为不再互相交叉。
- 已继续按真实关系修正 `v2` 图的骨架：`Joetsu` 现在明确在 `Hokuriku` 上方，`Yamagata` 不再压进 `Hokuriku`，`Tohoku` 绿线也已真实延伸到 `Shin-Aomori` 再接 `Hokkaido`。
- 已回补 `DIARY-2026-04-03.md`，并确认当前仓库与会话中没有可直接执行的 Notion 集成入口。
- 已正式为 `v2` 选定 `Plan A`，并在 `V2_GEOMETRY_PLAN.md` 里定义“真实站点坐标 + 真实线路顺序 -> 几何渲染 -> 有限视觉整理”的地图实施路线。
- 已完成 `v2` 第一版数据驱动底座：新增 `scripts/dev/render_shinkansen_v2_from_geometry.py`，并生成 `data/shinkansen_v2_stations.json`、`data/shinkansen_v2_routes.json` 与 `visuals/shinkansen_v2_map_real_geometry.svg`。
## In Progress
- 正在继续打磨 `v1` 的开发期可玩性，同时把 `v2` 从手工 SVG 草图切换到“数据驱动出图”，并准备把当前 `geometry seed` 逐步替换成真实经纬度。
## Blockers
- 当前仓库和本会话里没有可用的 Notion 工具、脚本或配置，所以今天无法直接完成真正的 Notion 更新。
- `v2` 新干线图仍需继续逐条核对真实线路关系，暂时还不能当正式底图使用。
## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 规则只能新建版本，不能直接改旧规则文件。
- [2026-04-03] 不再为每个小改动都 commit / push；只在显著变化时同步，但有实质工作的一天仍需至少同步一次。
- [2026-04-02] 当前阶段不因优化焦虑提前换语言；优先保证 `data schema / rules / simulation I/O / frontend-engine JSON boundary` 独立。
- [2026-04-03] 第一轮 hunter mode 测试使用“runner 不移动、主动试玩 hunter”的方式先隔离验证 hunter 侧的信息展示与操作闭环。
- [2026-04-03] 产品路线当前固定为 `v1 山手线`、`v2 新干线全图`、`v3 东京全图`；在 `v1` 验证清楚前，不提前展开更大地图。
## Next
1. 把 `shinkansen_v2_stations.json` 里的 `geometry_seed` 逐步替换成真实经纬度或投影坐标。
2. 继续做 `v1` 的 hunter / runner 开发期实机试玩，只盯“是否顺手、是否清楚、是否能稳定验证规则”。
3. 继续核对 `v2` 站点顺序、分支点和标签布局，并迭代这张数据生成图。
