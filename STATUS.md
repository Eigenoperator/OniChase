# STATUS

## Current Focus
把第一版真实时刻表模拟器和双端试玩工具，从“能跑”推进到“能实际规划玩法、在线试玩与高效迭代”的开发底座。

## Done
- 已完成项目初始化、记忆系统、规则版本管理与 GitHub 同步工作流。
- 已完成真实山手线站点、weekday 时刻表抓取、规范化、合并与可视化。
- 已完成第一版真实列车实例模拟器，支持 `actions` / `plan`、事件日志、`same_node` / `same_train` 抓捕，以及 `RULES_v0.6` 的边界判定。
- 已完成 `ENGINE_ARCHITECTURE.md`，明确 `data / rules / engine / interface / frontend` 五层边界。
- 已修正本地启动器：`START_ONICHASE_LOCAL.desktop` 现在直接调用脚本本体，`START_ONICHASE_LOCAL.sh` 会写入 `.onichase-launch.log` 便于排查启动失败。
- 已完成第一版本地桌面客户端原型：`local_client.py` 使用 `tkinter` 直接开窗，不依赖浏览器和本地 website。
- 已修正 `START_ONICHASE_CLIENT.desktop` 与 `START_ONICHASE_CLIENT.sh` 的执行权限，避免桌面环境把新的客户端启动器当成普通文本打开。
- 已为 `local_client.py` 增加鼠标左键拖拽地图，允许本地试玩时平移查看不同区域。
- 已按职责整理工作区：本地客户端归入 `app/`，网页源页归入 `ui/`，静态发布包归入 `docs/`，`scripts/` 拆分为 `engine / ingest / dev`，并补充了 `WORKSPACE.md`。
- 已为 `local_client.py` 补上第一版交互式动作流：可通过右侧按钮设起点、追加 `BOARD_TRAIN / RIDE_TO_STATION / WAIT_UNTIL`、撤销/清空步骤，并在窗口内直接运行模拟显示结果摘要。
- 已让车上视图显示这趟车接下来完整的站序；若是环线服务，则按一整圈显示到回到起始站为止。
- 已把本地客户端默认字号直接提到 `10` 档，并让左右两栏之间的分隔线可拖动，方便把右侧列表拉宽。
- 已把 `Result` 区升级成事件回放面板：运行模拟后会显示可滚动事件列表，并能查看当前选中事件的细节与双方状态。
- 已为本地客户端加入更明显的比赛时间流：先有 60 秒 `PLANNING` 倒计时、再进入 `LIVE` 游戏内时间推进；planning 阶段双方位置可见，live 阶段对手位置隐藏，且 live 中改 plan 会自动截断未执行的未来步骤。
- 已让本地客户端回放与地图联动：点击 `Result` 区事件后，地图会跳到该事件的 `state_after`，并在回放焦点下临时显示双方位置。
- 已把站内 planning 改成更用户友好的两步流：先大卡片选车，再从可横向拖动的后续站条里选下车站，选中的列车也会在地图上高亮。
- 已降低本地客户端右侧 planning 区在倒计时期间的闪烁，并在选车后自动把右栏滚到“选站”区域。
- 已继续强化“选站”可见性：选站条现在有更明显的提示文案和可见的横向滚动条。
- 已为 `STEP 2` 增加左图直选：选车后可直接点击左侧地图中被高亮的可达站点完成选站。
- 已为 `STEP 2` 增加右侧保底可见列表：即使横向站条不好看，也能直接在右侧竖向列表点 `Ride Here`。
- 已在选车后自动压缩 `STEP 1` 并给动作区更多高度，让 `STEP 2` 不再被上面的长发车列表挤掉。
- 已把 planning 输入切到 `plan cursor` 逻辑：在 `PLANNING` 阶段可以沿着已规划路线继续接着规划下一辆车，右上 `PLAN` 板也会显示当前 cursor 位置。
- 已把右上 `PLAN` 区从纯文本升级成路线板卡片，每段车程会以独立卡片显示。
- 已把 `PLAN BOARD` 提到右上最上方，并增加更醒目的标题底色和默认显示空间。
- 已修正 `PLANNING` 阶段的截断 bug：连续规划多辆车时，旧的未执行计划不会再被错误清掉。
- 已删除 `MATCH TABLE` 和 `IMMEDIATE OPTIONS` 两块 UI，让右侧更聚焦于 `PLAN BOARD`、动作区和回放区。
- 已把 `PLAN BOARD` 从右侧滚动内容中分离成固定区域，修正右侧动作区刷新后会把手动滚动位置弹回顶部的问题，并减少右侧 `PLAN BOARD` 与 `STEP 1 / STEP 2` 因整块重复重建导致的闪烁；玩家在车上时现在也会沿站间线路连续显示，不再只贴起终点站；同时已新增与本地客户端对齐的 `web_client` 和 GitHub Pages 发布链，并把“本地端与线上端保持同一主玩法流”正式写入 axioms；当前又补强了 Pages workflow 的 `configure-pages` 步骤并重新触发部署。

## In Progress
- 正在把本地客户端与新网页端一起推进到“更像正式玩法工作台”的阶段，重点是时间流、地图联动、输入闭环与在线试玩稳定性。

## Blockers

## Decisions
- [2026-03-30] 主测试主线使用“真实山手线 + 真实站点 + 真实时刻表”。
- [2026-03-30] 规则只能新建版本，不能直接改旧规则文件。
- [2026-03-30] 每次有实质项目变更后，默认都要 commit 并 push 到 GitHub。
- [2026-03-30] 当前本地 plan 测试默认使用 `06:00` 开局、Runner 赛外 1 分钟预规划、Hunter 默认原地等待。
- [2026-04-02] 当前阶段不因优化焦虑提前换语言；优先保证 `data schema / rules / simulation I/O / frontend-engine JSON boundary` 独立。

## Next
1. 继续把新的 `web_client` 往当前本地客户端能力靠近，比如补更完整的结果回放与事件步进。
2. 让 `local_client.py` 与 `web_client` 的站内点击都更直接地进入“从该站出发”的计划编辑流。
3. 跟进 GitHub Pages 的首次发布状态，确认公开 URL 能稳定打开并可直接试玩。
