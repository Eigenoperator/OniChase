# STATUS

## Current Focus
把第一版真实时刻表模拟器和网页工具，从“能跑”推进到“能实际规划玩法与高效迭代”的开发底座。

## Done
- 已完成项目初始化、记忆系统、规则版本管理与 GitHub 同步工作流。
- 已完成真实山手线站点、weekday 时刻表抓取、规范化、合并与可视化。
- 已完成第一版真实列车实例模拟器，支持 `actions` / `plan`、事件日志、`same_node` / `same_train` 抓捕，以及 `RULES_v0.6` 的边界判定。
- 已完成本地 `planner.html` 客户端原型：双击启动、圆环地图、Runner/Hunter 模式、plan 可视化轨迹、Runner plan test preset。
- 已完成 `ENGINE_ARCHITECTURE.md`，明确 `data / rules / engine / interface / frontend` 五层边界。

## In Progress
- 正在把 `planner.html` 接到本地模拟执行链上，让它不只生成 JSON，也能直接跑出结果。
- 正在把 engine 边界继续收紧，准备补 `RESULT_SCHEMA` / `REPLAY_SCHEMA` / `DATASET_SCHEMA`。

## Blockers
- 核心题材、长期玩法范围、目标平台仍未最终锁定。
- 当前还没有把网页客户端直接接到本地模拟结果回传，所以玩法验证效率仍受限。

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 规则只能新建版本，不能直接改旧规则文件。
- [2026-03-30] 每次有实质项目变更后，默认都要 commit 并 push 到 GitHub。
- [2026-03-30] 当前本地 plan 测试默认使用 `06:00` 开局、Runner 赛外 1 分钟预规划、Hunter 默认原地等待。
- [2026-04-02] 当前阶段不因优化焦虑提前换语言；优先保证 `data schema / rules / simulation I/O / frontend-engine JSON boundary` 独立。

## Next
1. 让 `planner.html` 能直接触发本地模拟并展示结果，而不是只导出 scenario JSON。
2. 补 `RESULT_SCHEMA.md`、`REPLAY_SCHEMA.md`、`DATASET_SCHEMA.md`，继续强化 engine-interface 边界。
3. 用新的 runner-plan 测试预设，验证首班车选择、临时下车、Hunter 静止时的人队优势。
