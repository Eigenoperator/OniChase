# STATUS

## Current Focus
当前最重要的一件事是什么？
建立真实山手线的站点与时刻表数据层，作为第一版可运行游戏地图基础。

## Done
- 完成身份与协作规则初始化。
- 读取并启用 `AXIOMS.md`。
- 建立基础控制文件与记忆结构。
- 将 `STATUS.md` 重写为标准模板。
- 将 daily memory 格式统一为固定 schema。
- 读取 `rule/RULES_v0.5.md` 中的 v0.5 规则并完成英文工作版翻译。
- 固化规则文件保护原则：规则改动前先询问 Scorp，且不直接改旧规则。
- 将规则文件名从 `A` 系列整理为 `RULES_v0.5` 系列。
- 固化 `rule/` 目录命名规范：`RULES_vX.Y.md` 与 `RULES_vX.Y-EN.md`。
- 新建 `SCHEMA.md`，定义第一版核心数据结构草案。
- 新建 `STATE_MACHINE.md`，定义最小对局状态机与状态转移。
- 确认 Candidate B 不再作为主要测试地图方向，转向“真实山手线 + 真实站点 + 真实时刻表”。
- 新建 `YAMANOTE_IMPLEMENTATION_PLAN.md`，定义真实山手线数据化与模拟实现计划。
- 删除所有 Candidate B 相关代码、数据与文档文件。
- 新建 `data/yamanote_stations.json`，写入真实山手线 30 站基础数据。
- 将“脚本面向真实游戏，不面向一次性测试图”写入 `AXIOMS.md`。
- 新建 `visuals/yamanote_line.svg`，可视化真实山手线 30 站环线示意图。
- 更新 `MEMORY.md`，补充当前项目主线、稳定规则、数据方向与已废弃分支。
- 调研 JR East 官方时刻表结构，并新建 `YAMANOTE_TIMETABLE_EXTRACTION.md`。
- 根据 Scorp 的偏好更新 train 数据建模：列车实例不绑定单一线路，线路归属记录到 stop-time 层。
- 新建 `scripts/validate_station_dataset.py`，并运行通过。
- 新建 `scripts/discover_jreast_timetable.py`，作为 JR East 官方时刻表发现脚本。
- 新建 `scripts/parse_jreast_train_detail.py`，可将 JR East train-detail 页解析成按列车存储的 train instances。
- 获取并保存第一批真实山手线 weekday train-instance 数据到 `data/yamanote_weekday_train_instances_seed.json`。
- 新建 `scripts/normalize_train_instances_with_station_mapping.py`，并产出带规范 `station_id` 的 normalized 列车数据文件。
- 新建 `scripts/build_jreast_train_instances_from_station_timetable.py`，实现从单站整日 timetable 页批量抓取 train-detail 并按列车去重。
- 从滨松町站 weekday counterclockwise 官方时刻表页面成功抓取并保存 `246` 趟真实山手线列车到 `data/yamanote_weekday_from_hamamatsucho_counterclockwise.json`。
- 从滨松町站 weekday clockwise 官方时刻表页面成功抓取并保存 `265` 趟真实山手线列车到 `data/yamanote_weekday_from_hamamatsucho_clockwise.json`。
- 为环线场景补强 train 建模：支持重复站、`loop_pass_index` 与连续 service instance 语义。
- 将脚本命名重构为按职责或外部来源格式命名，而不是按当前数据集临时命名。
- 新建 `scripts/validate_train_instances_dataset.py`，为按列车存储的时刻表数据提供结构与时序校验。
- 抽出 `scripts/train_instance_normalization.py` 作为共用规范化层，并让 builder / normalize 脚本统一复用。
- 将滨松町站 weekday 两个方向的整日数据补齐 `service_instance_id` 与 `loop_pass_index`，并重新校验通过。
- 新建 `scripts/merge_train_instance_datasets.py`，完成两个方向整日数据的合并与去重检查。
- 产出 `data/yamanote_weekday_train_instances_merged.json`，得到 `511` 趟可直接用于模拟器的 weekday 山手线列车实例。
- 新建 `scripts/render_train_timetable_svg.py`，并产出 `visuals/yamanote_weekday_timetable.svg` 作为全天时空图可视化。
- 新建 `SIMULATION_INPUT.md`，定义第一版真实时刻表模拟器的玩家动作输入格式。
- 新建 `scripts/simulate_match_from_train_instances.py`，实现基于真实 train instances 的最小两人对局模拟。
- 新建样例场景 `data/scenarios/yamanote_weekday_same_train_capture_v0_1.json`，并成功复现真实 `same_train` 抓捕：`720G`，`08:11`。
- 将模拟器输出升级为完整 `match_event_log`，并在每个事件上提供 `state_before / state_after / state_snapshot`。
- 新建结果文件 `data/results/yamanote_weekday_same_train_capture_v0_1.result.json`，可直接检查真实样例的逐事件回放。
- 将抓捕判定改为事件驱动即时裁定，并在 `CAPTURE` 事件中记录 `trigger_event_type`。
- 新建真实 `same_node` 验证场景 `data/scenarios/yamanote_weekday_arrival_into_waiting_hunter_v0_1.json`，成功复现 `08:11` 于 `UENO` 的到站即抓捕。
- 新建 `rule/RULES_v0.6.md` 与 `rule/RULES_v0.6-EN.md`，正式记录“同分钟下车/上车交错”边界规则。
- 用真实山手线样例验证了 `RULES_v0.6`：同车交错抓捕成功，异车交错抓捕失败。
- 将“每个新规则版本文件顶部必须先写 Main Change”写入 `AXIOMS.md`，并补齐到 `RULES_v0.6` 顶部。
- 新建 `PLANNING_FORMAT.md`，定义 planning-friendly 输入层与第一种候选步骤 `BOARD_ANY_OF`。
- 让模拟器支持 `plan` 模式输入，并输出 `resolved_actions` 与 `PLAN_RESOLUTION` 事件。
- 为事件日志补充 `event_scope`、`timeline_lane`、`event_family`，便于未来 UI 回放分轨展示。
- 新建 `data/scenarios/yamanote_weekday_plan_fallback_v0_1.json`，验证候选列车计划会正确回退到首个可赶上的真实班次。
- 新建 `debug_gui.html`，提供本地调试 GUI 用于加载 replay、查看事件流、检查双方状态与山手线站位。
- 新建 `DEBUG_GUI.md`，写明 GUI 的用途、加载方式与本地启动命令。
- 新建 `planner.html`，把网页工具方向转成 planning-first：可选起点、组行动链、浏览真实可上车班次、生成 scenario JSON。
- 新建 `PLANNER_GUI.md`，说明 planning GUI 的用途、启动方式与当前支持的步骤类型。
- 初始化本地 git 仓库，连接 `git@github.com:Eigenoperator/OniChase.git`，并完成首轮项目同步到 GitHub。
- 新建 `scripts/run_local_site.py`、`START_ONICHASE_LOCAL.sh`、`START_ONICHASE_LOCAL.desktop`，提供可双击启动的本地网站入口。
- 实测本地启动器可成功拉起 `planner.html`，并会自动选择空闲端口。
- 将 `planner.html` 重构为更接近客户端的玩法原型：支持 Runner / Hunter 模式切换，主屏为山手线地图，左上 HUD 显示时间与当前位置，在列车上时展示后续站点，右侧显示当前 plan。
- 将 `planner.html` 的山手线地图改为典型圆环布局：按真实站序均分圆周、闭合主环路径，并将站名沿径向向外排布，避免原先不自然的折线感。
- 将“每次有实质变更后都要 commit 并 push 到 GitHub”写入 `AXIOMS.md`，作为项目默认同步规则。
- 为 `planner.html` 增加 runner-plan 测试预设：默认 `06:00` 开局、Runner 使用 `plan` 模式、Hunter 默认原地等待到结束，并在界面中明确显示当前测试假设。
- 为 `planner.html` 增加 `Cut Future` 与 Hunter 被动等待解除逻辑，方便测试“执行中修改后续计划”的玩法感受。
- 为 `planner.html` 增加当前玩家的地图计划轨迹：把当前 plan 直接画成虚线路径和编号 waypoint，降低抽象规划门槛。
- 修正 `Plan Test Mode` 文案：明确“06:00 才开始游戏内时间”，Runner 的 1 分钟准备发生在赛外。
- 按自然日首条消息规则检查并回补缺失的 `diary/DIARY-2026-03-30.md`。

## In Progress
- 正在把第一版真实时刻表模拟器和网页工具从“可运行”推进到“可实际规划玩法与高效迭代”的开发底座。

## Blockers
- 游戏题材、核心玩法、目标平台尚未确定。

## Decisions
- [2026-03-30] 所有 markdown 文件名统一使用大写。
- [2026-03-30] 开始前读取 `STATUS.md`，结束时必须更新 `Done / In Progress / Blockers / Next`。
- [2026-03-30] Daily memory 使用 `# Daily Memory - YYYY-MM-DD` 标题和完整时间戳条目格式。
- [2026-03-30] `rule/RULES_v0.5.md` 的规则草案 v0.5 作为当前游戏设计与技术拆解的基线。
- [2026-03-30] 任何规则变更都必须先征求 Scorp 同意，且只能新建版本，不直接编辑旧规则文件。
- [2026-03-30] `rule/` 目录规则文件统一命名为 `RULES_vX.Y.md`，英文工作版统一命名为 `RULES_vX.Y-EN.md`。
- [2026-03-30] 为了支持真实列车选择，测试地图主线改为“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 编写脚本时应面向真实游戏架构与真实生产数据流，而不是一次性测试图逻辑。
- [2026-03-30] 第一版 weekday 山手线数据库采用“按列车实例合并”而不是“按站点页继续分裂存储”，并在 train-instance 层保留 `direction_label`。
- [2026-03-30] 若同一分钟内一人到站进入 `node`、另一人从该 `node` 上车离开，则仅在双方属于同一趟车实例时抓捕成功；异车交错不抓捕。
- [2026-03-30] `planner.html` 的山手线主地图视觉采用标准圆环表达，优先服务于玩家对环线空间的直觉理解。
- [2026-03-30] 每次有实质项目变更后，默认都要将当前状态 commit 并 push 到 GitHub。
- [2026-03-30] 当前本地 plan 测试默认使用 `06:00` 开局、Runner 赛外 1 分钟预规划、Hunter 默认原地等待的快速验证模式。
- [2026-03-30] 当前玩家的 plan 应尽量在地图上可视化，而不是只显示为右侧步骤列表。

## Next
1. 让 `planner.html` 能直接触发本地模拟并展示结果，而不是只导出 scenario JSON。
2. 围绕新的 runner-plan 测试预设，跑一轮真实玩法问题验证，例如首班车选择、临时下车、Hunter 静止时的人队优势。
3. 扩展 planning 步骤种类，例如 transfer preference、wait-for-one-of、多段候选链。
