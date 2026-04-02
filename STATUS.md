# STATUS

## Current Focus
把第一版真实时刻表模拟器和网页工具，从“能跑”推进到“能实际规划玩法与高效迭代”的开发底座。

## Done
- 已完成项目初始化、记忆系统、规则版本管理与 GitHub 同步工作流。
- 已完成真实山手线站点、weekday 时刻表抓取、规范化、合并与可视化。
- 已完成第一版真实列车实例模拟器，支持 `actions` / `plan`、事件日志、`same_node` / `same_train` 抓捕，以及 `RULES_v0.6` 的边界判定。
- 已完成本地 `planner.html` 客户端原型：双击启动、圆环地图、Runner/Hunter 模式、plan 可视化轨迹、Runner plan test preset。
- 已将 `planner.html` 进一步提升为更像可试玩客户端的 UI：更强的地图主体感、双方 match table、底部 quickbar、地图 legend、主动/被动路线分层显示。
- 已完成 `ENGINE_ARCHITECTURE.md`，明确 `data / rules / engine / interface / frontend` 五层边界。
- 已修正本地启动器：`START_ONICHASE_LOCAL.desktop` 现在直接调用脚本本体，`START_ONICHASE_LOCAL.sh` 会写入 `.onichase-launch.log` 便于排查启动失败。
- 已完成第一版本地桌面客户端原型：`local_client.py` 使用 `tkinter` 直接开窗，不依赖浏览器和本地 website。

## In Progress
- 正在决定是否把主试玩入口从 `planner.html` 彻底切到新的 `local_client.py` 本地桌面客户端。
- 正在把本地客户端从“窗口壳”继续推进到“可直接跑局”的本地玩法工作台。
- 正在把 engine 边界继续收紧，准备补 `RESULT_SCHEMA` / `REPLAY_SCHEMA` / `DATASET_SCHEMA`。

## Blockers
- 核心题材、长期玩法范围、目标平台仍未最终锁定。
- 当前还没有把网页客户端直接接到本地模拟结果回传，所以玩法验证效率仍受限。
- 当前本地桌面客户端还是第一版壳层，还没有在窗口内直接执行模拟或编辑步骤。

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 规则只能新建版本，不能直接改旧规则文件。
- [2026-03-30] 每次有实质项目变更后，默认都要 commit 并 push 到 GitHub。
- [2026-03-30] 当前本地 plan 测试默认使用 `06:00` 开局、Runner 赛外 1 分钟预规划、Hunter 默认原地等待。
- [2026-04-02] 当前阶段不因优化焦虑提前换语言；优先保证 `data schema / rules / simulation I/O / frontend-engine JSON boundary` 独立。

## Next
1. 让 `planner.html` 能直接触发本地模拟并展示结果，而不是只导出 scenario JSON。
2. 把 `local_client.py` 从窗口原型推进到可交互：先补本地 step 编辑和窗口内模拟执行。
3. 补 `RESULT_SCHEMA.md`、`REPLAY_SCHEMA.md`、`DATASET_SCHEMA.md`，继续强化 engine-interface 边界。
