# STATUS

## Current Focus
把 `v1` 山手线试玩底座保持稳定，同时把 `v2` 全国新干线真实列车数据继续补齐并收成可靠的全国 train-instance 管线。

## Done
- 已完成 `v1` 山手线真实站点、weekday 时刻表、合并列车实例、可视化与第一版可玩客户端。
- 已完成 `v1` hunter mode 第一轮开发：信息限制、live 抓捕判定、结束标记、抓捕说明卡。
- 已完成 `v2` 新干线全图的数据驱动地图底座：真实站点、真实线路顺序、真实坐标、自动标签避让、地图渲染脚本。
- 已完成 `v2` 官方时刻表入口清单与站点清单，接通 `JR East / JR West / JR Kyushu` 多源 train-detail 抓取链。
- 已生成 `data/shinkansen_v2_weekday_train_instances_merged.json`，当前合并后为 `1145` 趟 weekday 真实新干线列车实例。
- 已补上 `Joetsu` 的 `Niigata -> Tokyo` 上行，以及 `Hokuriku` 的 `Nagano` 上下行和 `Tsuruga -> Tokyo` 上行。
- 已新增 `visuals/shinkansen_v2_weekday_timetable.svg`，按线路分 panel 可视化 `v2` 全国新干线 weekday 时刻图。
- 已打通 `JR Central` 的 `station-guide -> ResultControl -> tokainr.cgi` 官方链，并新增 `data/shinkansen_v2_jrcentral_tokaido_weekday_supplement.json`，补入 `43` 趟东海道中途始发/短折返真实班次。
- 已修正 `JR Kyushu / Nishi-Kyushu` 双栏 `Kamome` 详情页解析错误，`Takeo-Onsen -> Nagasaki` 与 `Nagasaki -> Takeo-Onsen` 现在都能正确进入全国合并库。
- 已修正全国合并逻辑，跨运营商同一趟真实列车现在会按真实服务名/号合并，不再把 `JR Central` 的东海道补丁短版和 `JR West / JR East` 的全程版重复算两趟。

## In Progress
- 正在继续查 `v2` 是否还缺明显的短折返 / 中途始发终到班次，当前重点是全国合并后的全网抽查。
- 正在把 `v2` 的 source inventory、station timetable inventory 和合并规则收成长期可复用的 ingestion 底座。

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
1. 继续抽查 `v2` 合并后的起终点分布，确认 `Tokaido / Sanyo / Hokuriku / Joetsu / Kyushu` 是否还缺明显短折返。
2. 继续核对 `JR Kyushu / Nishi-Kyushu` 之外是否还存在类似的双栏 / 多服务详情页解析陷阱。
3. 把这轮全国数据体检整理成明确的 anomaly checklist，后面按线路逐项收。
