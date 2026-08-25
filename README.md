# DeepSeek Character Agent UI

面向 DeepSeek Harness 的人物化 Agent 交互界面。项目不把角色当作聊天窗口旁的装饰，而是让角色直接承载 Agent 的真实运行状态：用户输入、思考、流式输出、工具执行、等待、成功、错误、睡眠与唤醒。

> **Work in progress。** 状态运行时和人物素材流水线已经进入实现阶段，但完整 React 界面、Harness 适配、安装回滚及真实端到端验证尚未完成。本仓库目前不能作为可安装发行版使用。

当前实现位于 [`feature/persona-ui-mvp`](https://github.com/sus66618/deepseek-character-agent-ui/tree/feature/persona-ui-mvp)；`main` 保留项目说明与经批准的设计文档。

## 项目亮点

- 以稳定的 `CharacterController` 隔离 Agent 业务状态与人物渲染，短期分层 PNG 和长期 Live2D 共用同一套行为契约。
- 使用带优先级和过期事件保护的状态机，避免旧事件覆盖新的 Agent 状态。
- 待机动作采用可注入随机源、动作权重和独立冷却；无真实输入 150–210 秒后进入睡眠，鼠标移动不会误唤醒。
- 视线跟随采用有界指数平滑，并对非法时间步和非有限输入做安全降级。
- 人物素材构建包含源文件哈希、透明主体分割、23 层 manifest、PSD 分组与 fail-closed 校验，不以“文件非空”冒充视觉可用。
- 设计了版本门控、备份优先、可卸载和可回滚的 Harness 接入方案；该部分仍待真实集成验证。

## 当前进度

| 模块 | 状态 | 当前证据 |
|---|---|---|
| TypeScript / React / Vite / Vitest / Playwright 工程 | 已完成 | `typecheck`、构建与浏览器 smoke test |
| 人物状态契约与状态机 | 已完成 | 事件优先级、stale-event、睡眠/唤醒单元测试 |
| 待机动作、视线与动作仲裁 | 已完成 | 权重、冷却、150–210 秒睡眠边界、gaze 与 channel 测试 |
| 透明人物主体 | 已完成并通过视觉审查 | 1024×1536 RGBA，RGB 保持原图，CPU 本地分割与多背景 QA |
| 23 层素材与 PSD | 机械校验通过，视觉返工中 | validator 可识别缺文件、重复 z、错误尺寸、无 alpha、越界 anchor 等；眼睑、嘴型和头发接缝尚未通过视觉验收 |
| 分层 PNG Renderer | 未开始 | 计划 Task 6 |
| 人物主界面与任务泡泡 | 未开始 | 计划 Task 7–8 |
| Harness rc.6 适配与原生回退 | 未开始 | 计划 Task 9–10 |
| 安装、卸载、重启与回滚 E2E | 未开始 | 计划 Task 11–12 |
| Live2D | 长期路线 | 在分层 PNG MVP 通过真实 Harness 验收后启动 |

当前分支的自动化基线：

```text
Vitest:              45 passed
TypeScript:          PASS
Asset validator:     PASS (23 files, structural validation only)
Harness deployment:  NOT YET VERIFIED
```

这里特意区分“结构校验通过”和“视觉验收通过”：已有一版闭眼、嘴型和头发偏移动画被人工审查打回，因此没有把测试全绿写成产品完成。

## 架构

```text
DeepSeek Harness events
          │
          ▼
    HarnessBridge / rc6 adapter       ← 待实现
          │
          ▼
    CharacterController
      ├─ IdleActionScheduler
      ├─ GazeController
      └─ MotionCoordinator
          │
          ▼
    CharacterRenderer
      ├─ LayeredPngRenderer           ← MVP
      └─ Live2DRenderer               ← 长期替换
          │
          ▼
    PersonaShell
      ├─ 人物舞台与说话气泡
      ├─ 任务泡泡 / 新任务 / 溢出浏览
      ├─ 长矩形输入区
      └─ 完整输出阅读层
```

核心边界是：模型或 Harness 只产生事件，控制器决定角色状态，渲染器只消费动作命令。更换人物渲染技术时不改 Agent 行为层。

## 交互目标

- 默认界面以人物为视觉主体，不保留传统长输出框。
- Agent 的简练回复显示在人物说话气泡中，点击后打开完整 Markdown、代码、表格和工具记录。
- 新任务、近期任务和历史任务由人物周围的泡泡承载，超出可见数量后进入 `…` 浏览器。
- 人物对 `idle`、`user_input`、`thinking`、`streaming`、`tool_running`、`waiting_user`、`success`、`error`、`sleeping` 和 `waking` 做可辨识反应。
- 支持 `off`、`gentle`、`full` 动态级别和 `prefers-reduced-motion`。

## 本地验证

项目初始目标运行时为 Node.js 22.23.2。

```powershell
npm install --legacy-peer-deps
npm run typecheck
npm test
node scripts/validate-character-assets.mjs
npm run build
npm run test:e2e
```

说明：当前 `test:e2e` 只有独立预览 smoke test，不代表 Harness 真实集成已经通过。

## 仓库结构

```text
src/character/                       # 状态、动作、视线和渲染契约
assets/character/deepseek-v2/        # 原始副本、透明主体、分层 PNG 与 PSD
scripts/                             # 可复现素材构建和 fail-closed validator
tests/unit/                          # TypeScript 行为与负例测试
tests/python/                        # 图像构建与视觉代理指标测试
tests/e2e/                           # 浏览器预览与后续 Harness E2E
evidence/                            # 哈希、视觉 QA 和阶段性证据
docs/superpowers/specs/              # 产品与架构规格
docs/superpowers/plans/              # 可执行实施计划
docs/progress/                       # 中断恢复点和诚实的验收记录
```

## 设计与计划

- [完整设计规格](./docs/superpowers/specs/2026-08-18-deepseek-character-agent-ui-design.md)
- [分阶段实施计划](./docs/superpowers/plans/2026-08-18-deepseek-character-agent-ui.md)
- [最新视觉返工存档](https://github.com/sus66618/deepseek-character-agent-ui/blob/feature/persona-ui-mvp/docs/progress/2026-08-20-visual-fix-checkpoint.md)

## MVP 完成标准

只有满足以下条件，仓库才会标记为可用 MVP：

1. 人物动作由真实 Harness 事件驱动，而不是定时伪装工作状态。
2. 任务可以创建、切换和浏览，简练回复与完整输出均可访问。
3. 睡眠、真实输入唤醒、减少动态和低性能降级可复现。
4. 未知 Harness 版本 fail closed，原生界面仍可使用。
5. 真实浏览器、Harness 重启、卸载和备份回滚均留下可核验记录。
