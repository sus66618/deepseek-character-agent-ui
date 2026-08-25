# DeepSeek Character Agent UI

一个面向 DeepSeek Harness 的人物化 Agent 交互界面设计项目。它尝试让角色成为 Agent 状态的主要视觉表达：角色根据用户输入、思考、流式输出、工具执行、等待、成功或错误等真实事件切换动作，同时保留任务管理和完整技术输出。

> **项目状态：设计阶段。** 当前仓库包含产品规格和实施计划，尚未包含可运行界面、角色素材或 Harness 集成代码。这里记录的是拟实现方案，不代表功能已经完成。

## 设计目标

- 用人物舞台取代传统聊天窗口的主视觉，而不是简单增加装饰角色
- 由真实 Agent 事件驱动动画，不伪造工作状态
- 气泡展示精简结果，同时保留完整 Markdown、代码、表格和工具记录
- 兼顾任务切换、键盘访问、减少动态效果与低性能降级
- 使用可替换渲染层，先支持分层 PNG，再演进到 Live2D
- 通过可回滚的适配层接入 Harness

## 交互概念

界面由顶部栏、人物主舞台、任务泡泡、说话气泡和专注阅读层组成。计划支持 `idle`、`user_input`、`thinking`、`streaming`、`tool_running`、`waiting_user`、`success`、`error`、`sleeping` 和 `waking` 等角色状态。

## 计划架构

```text
Harness 会话、消息、工具和输入事件
                 │
                 ▼
        HarnessStateAdapter
                 │
                 ▼
        CharacterController
        ├── IdleActionScheduler
        ├── GazeController
        └── MotionCoordinator
                 │
        CharacterRenderer 接口
          ├── LayeredPngRenderer
          └── Live2DRenderer
```

- `HarnessStateAdapter`：将 Harness 事件映射为稳定的角色状态。
- `CharacterController`：处理状态优先级、动作抢占和恢复。
- `MotionCoordinator`：协调身体、表情、道具与镜头动作。
- `CharacterRenderer`：隔离业务状态和具体人物渲染方案。
- `TaskBubbleController`：管理任务泡泡、布局和安全区。
- `ReplyPresenter`：生成精简展示并保留完整输出。

## 路线图

- [ ] 完成交互原型与关键状态页面
- [ ] 建立角色分层规范和素材清单
- [ ] 实现状态适配器与角色控制器
- [ ] 实现分层 PNG 渲染器
- [ ] 接入任务泡泡、输入区和专注阅读层
- [ ] 制作可安装、可卸载、可回滚的 Harness 集成方案
- [ ] 完成功能、性能、可访问性和升级回归测试
- [ ] 评估并替换为 Live2D 渲染器

## 仓库内容

```text
docs/superpowers/
├── specs/   # 产品、交互、架构和验收设计
└── plans/   # 分阶段实施计划
```

- [完整设计规格](./docs/superpowers/specs/2026-08-18-deepseek-character-agent-ui-design.md)
- [实施计划](./docs/superpowers/plans/2026-08-18-deepseek-character-agent-ui.md)

## 完成标准

只有在人物动作由真实 Agent 状态驱动、任务可以创建和切换、精简与完整输出均可查看、睡眠唤醒可复现、降级路径有效，并且 Harness 原有关键功能没有回归时，项目才会被标记为可用 MVP。

## 说明

仓库中的架构名称、性能目标和 Live2D 路线均属于设计决策。后续实现应以实际代码、测试和运行证据更新本文，不能把路线图当成发布记录。
