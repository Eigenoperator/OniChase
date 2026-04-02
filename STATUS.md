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
- 已修正 `START_ONICHASE_CLIENT.desktop` 与 `START_ONICHASE_CLIENT.sh` 的执行权限，避免桌面环境把新的客户端启动器当成普通文本打开。
- 已为 `local_client.py` 增加鼠标左键拖拽地图，允许本地试玩时平移查看不同区域。
- 已为 `local_client.py` 增加滚轮缩放和站点点击选中，支持更自然的本地地图浏览。
- 已按职责整理工作区：本地客户端归入 `app/`，网页原型归入 `ui/`，`scripts/` 拆分为 `engine / ingest / dev`，并补充了 `WORKSPACE.md`。
- 已为 `local_client.py` 补上第一版交互式动作流：可通过右侧按钮设起点、追加 `BOARD_TRAIN / RIDE_TO_STATION / WAIT_UNTIL`、撤销/清空步骤，并在窗口内直接运行模拟显示结果摘要。
- 已把本地客户端的计划输入改成更贴近玩法的状态驱动式交互：站内直接列出当前站的即将发车车次；上车后直接列出该车后续可下站点；在车上点击可达站点也能直接加入下车动作。
- 已让车上视图显示这趟车接下来完整的站序；若是环线服务，则按一整圈显示到回到起始站为止。
- 已让本地客户端右侧整列信息在小窗口下支持滚轮滚动，方便浏览长的发车列表、可下车站点和结果摘要。
- 已为本地客户端加入 `Settings` 按钮和首个设置项：现在可以在设置窗里调整整个 UI 的字体大小。
- 已把本地客户端默认字体基线调大，打开客户端时无需先进设置就能得到更易读的首屏字号。
- 已进一步把本地客户端默认字号显著调大，并提高 `Settings` 中字体大小滑条的上限，方便直接得到更大的 UI。
- 已把本地客户端默认字号直接提到 `10` 档，并让左右两栏之间的分隔线可拖动，方便把右侧列表拉宽。
- 已让右侧栏内部也支持拖动分隔，`Info / Actions / Result` 三块区域现在可以纵向自行分配高度。
- 已修正本地客户端启动兼容性问题：移除了 `tkinter.PanedWindow` 不支持的参数，避免客户端在构建界面时直接崩溃。

## In Progress
- 正在决定是否把主试玩入口从 `planner.html` 彻底切到新的 `local_client.py` 本地桌面客户端。
- 正在把本地客户端从“可直接跑局”继续推进到“更像正式玩法工作台”的阶段。
- 正在把 engine 边界继续收紧，准备补 `RESULT_SCHEMA` / `REPLAY_SCHEMA` / `DATASET_SCHEMA`。

## Blockers
- 核心题材、长期玩法范围、目标平台仍未最终锁定。
- 当前还没有把网页客户端直接接到本地模拟结果回传，所以玩法验证效率仍受限。
- 当前本地桌面客户端虽然已能按当前状态直接选车和选站，但还没有完整的表单式 step 编辑器。
- 当前地图虽然已有平移、缩放、站点选中，且车上点击可达站点可直接下车，但站内点击站点还没有完全直接变成“换站出发”的编辑闭环。

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 规则只能新建版本，不能直接改旧规则文件。
- [2026-03-30] 每次有实质项目变更后，默认都要 commit 并 push 到 GitHub。
- [2026-03-30] 当前本地 plan 测试默认使用 `06:00` 开局、Runner 赛外 1 分钟预规划、Hunter 默认原地等待。
- [2026-04-02] 当前阶段不因优化焦虑提前换语言；优先保证 `data schema / rules / simulation I/O / frontend-engine JSON boundary` 独立。

## Next
1. 让 `planner.html` 能直接触发本地模拟并展示结果，而不是只导出 scenario JSON。
2. 让 `local_client.py` 的站内点击也能更直接地进入“从该站出发”的计划编辑流。
3. 为本地客户端补更清晰的结果回放区，而不只是一段 simulation 摘要。
