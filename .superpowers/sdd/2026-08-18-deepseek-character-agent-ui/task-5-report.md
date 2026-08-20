# Task 5 资产包恢复报告

状态：`BLOCKED`

本报告记录 2026-08-20 在 `feature/persona-ui-mvp`、基线提交 `a741704f2ee7fa368934fbb9285f18d886c525d7` 上的恢复尝试。当前工作树中的产物均为未验收中间件，不得作为 Task 5 完成证据。

## 验收结论

| 验收项 | 结果 | 证据或原因 |
| --- | --- | --- |
| 原图先行视觉检查 | PASS | 已用 `view_image` 检查完整原图，并生成/检查 `evidence/assets/work/source-detail-200.png` 与 `boots-source-200.png` 的 200% 像素参考。 |
| 不可变原图复制与 SHA-256 | PASS | 原图与 `source/original.png` 哈希一致。原图未覆盖。 |
| 23 张真实 1024×1536 RGBA 层 | FAIL | 主体 alpha matte 未达到无背景块、无人物孔洞的最低视觉门槛，因此没有继续导出伪层。 |
| 7 个指定分组的 PSD | FAIL | 未创建。没有可接受的 23 层像素时，创建空壳 PSD 会是假通过。 |
| manifest | DRAFT ONLY | 基线提交中的 manifest 保持草稿状态，未作为通过项。 |
| validator | FAIL | `scripts/validate-character-assets.mjs` 尚不存在；真实命令退出 1。 |
| 单元测试 | RED | 按 TDD 先扩充真实 CLI/失败路径测试；当前 9 项中 2 通过、7 失败，失败原因是 validator 尚不存在。 |
| 六张 seam QA | FAIL | 未生成最终 neutral/blink/gaze/hair/hand/tail 六图。中间 matte 图已实际检查并被拒绝。 |
| typecheck | PASS | `npm run typecheck` 退出 0。 |
| 提交 | NONE | 未提交失败资产；HEAD 仍为 `a741704f2ee7fa368934fbb9285f18d886c525d7`。 |

## 源文件完整性

- 原始路径：`E:/adventure/ai_code/codex_image/character/ai-anime-girl-deepseek-v2.png`
- 工作区副本：`assets/character/deepseek-v2/source/original.png`
- 尺寸：`1024×1536`
- 原图像素格式：`RGB / 24 bpp`，无 alpha
- 预期、原图、副本 SHA-256：`24DF7985AE880E21CB5EB7FF6C811631C00CEFC82F9BE4C91D580350C61A79D5`
- 字节数：`2082244`
- 结构化证据：`evidence/asset-source.json`

## 使用的工具

- built-in `view_image`：检查原图、200% 细节、深色底 matte 与 AI 粗先验。
- Python `3.11.15`、Pillow、NumPy：确定性复制、裁切、蒙版、RGBA 合成与哈希统计。
- OpenCV headless `4.12.0`：固定随机种子 `20260820` 的 GrabCut、连通域、形态学与边缘羽化。安装在任务临时目录 `C:/Users/UserX/AppData/Local/Temp/codex-task5-opencv-4.12.0.88`，不写入项目依赖。
- `psd-tools 1.18.0`：已在任务临时目录准备，并依据官方写入 API设计分组生成路径；因 matte 失败，未创建误导性 PSD。
- built-in `image_gen`：仅尝试生成透明主体粗蒙版参考；没有调用 CLI/API、没有使用密钥，也没有调用其他外部上传服务。
- Node.js `22.14.0`、Vitest `4.1.8`、TypeScript：测试与类型检查。

## built-in image_gen 记录

调用模式：built-in edit；输入图同时作为 edit target 与 identity reference。

默认输出路径：

`C:/Users/UserX/.codex/generated_images/01a01e51-0af1-7162-a96a-d44cbc1d2876/exec-545641b1-2c5f-43bc-b22d-368af5d0f810.png`

工作区副本：

`assets/character/deepseek-v2/source/ai-matte-reference.png`

工作区副本 SHA-256：

`177398BFC9CAFCD94A19AE1AED50BA5DAE1990CB4291D2CEFB03040929CFC84B`

最终 prompt：

```text
Use case: background-extraction
Asset type: identity-preserving full-body character matte reference for a layered UI asset
Primary request: Remove only the pale background, sonar rings, floor reflection, and loose background bubbles. Return the exact same complete character as a clean transparent-background cutout.
Input image: Image 1 is both the edit target and the strict identity reference.
Subject: Preserve the complete blue-haired anime whale-girl character, including both cat ears, every hair curl and loose strand, face, both eyes, both hands and fingers, handheld glowing orb, white cape and skirt edges, crossed legs, both boots, accessories, and the full whale tail through both tail fins.
Composition/framing: Preserve the original 1024x1536 portrait canvas, exact pose, scale, placement, silhouette, and full-body framing; no cropping.
Constraints: Change only the background to genuine transparency. Preserve identity, facial geometry, line art, colors, shading, costume details, anatomy, accessories, and tail attachment exactly. Keep the handheld orb/core because it is part of the character package. Produce a real alpha channel with crisp antialiased edges and transparent gaps between hair curls, fingers, legs, boots, body, and tail. No opaque background pixels or floor shadow.
Avoid: regeneration drift, altered face or eyes, changed hands, simplified curls, missing garment edges, missing tail fins, white matte halos, transparent holes inside the character, original-position ghosts, text, watermark.
```

检查结果：输出尺寸为 `1024×1536`，但文件模式是 `RGB`，棋盘格被烘焙到像素中，没有 alpha 通道；同时人物轮廓和局部造型有生成漂移。因此它没有被当作最终层或最终 RGB，只尝试作为粗蒙版先验。深色底检查 `evidence/assets/work/ai-prior-original-dark.png` 显示整圈白色 halo，粗先验同样被拒绝。

## 本地蒙版与视觉检查

确定性脚本：`scripts/build-character-assets.py`。它实现了固定种子 GrabCut、人工前景/背景种子、关键白材质补回、层清单、PSD 分组结构与六类 QA 合成入口；由于 alpha gate 失败，脚本没有执行最终 23 层/PSD 交付阶段。

实际检查过的中间图：

- `evidence/assets/work/source-detail-200.png`：脸、双眼、双手、卷发、服装边缘、尾根/尾鳍的 200% 原图参考。
- `evidence/assets/work/boots-source-200.png`：双靴与地面反射的 200% 原图参考。
- `evidence/assets/work/subject-matte-preview.png`：本地 GrabCut + 人工蒙版在深色 checkerboard 上的最新结果。
- `evidence/assets/work/ai-prior-original-dark.png`：built-in 输出所提粗先验套回原始 RGB 后的深色底结果。

拒绝原因：

- 本地 matte 仍在右耳、白靴等区域出现背景白块；早期版本还在脸、手、白披肩、裙边产生透明孔洞。
- AI 粗先验与原图轮廓不完全对齐，并包含烘焙棋盘格，套回原始 RGB 后形成连续白 halo。
- 这些缺陷会在 hair/hand/tail offset 时直接变成原位置残影、断裂或不透明色块，不满足 seam QA。

## 验证输出

```text
npm test -- tests/unit/asset-manifest.test.ts
Test Files  1 failed (1)
Tests       7 failed | 2 passed (9)
原因：Cannot find module scripts/validate-character-assets.mjs
```

```text
npm run typecheck
退出码 0
```

```text
node scripts/validate-character-assets.mjs
退出码 1
Error: Cannot find module scripts/validate-character-assets.mjs
```

```text
git diff --check
退出码 0
```

## 阻塞点与恢复条件

阻塞在人工蒙版/遮挡补底质量，而不是代码框架：单张 RGB 平面图中白披肩、白裙、白靴与浅色背景高度同色；卷发、手指、尾鳍又包含大量细小负空间。当前环境没有 Krita/GIMP/Photoshop 等人工像素编辑器，built-in image_gen 也没有返回真实透明通道。继续自动堆叠多边形会产生不可审计的假精度。

恢复 Task 5 至少需要以下任一条件：

1. 提供经人工检查的同尺寸透明主体 PNG/PSD；或
2. 提供可交互人工修边的栅格编辑器，并逐项完成脸、双眼、双手、卷发、服装边缘、尾根的 200% 修补；或
3. built-in image_gen 能返回真实 RGBA 且轮廓与原图对齐的背景提取结果，再以原图 RGB 做本地边缘修复。

在上述条件满足前，`ASSET_VALIDATION=PASS`、六张 seam QA PASS 与分组 PSD 都不能诚实声称完成。

---

## 2026-08-20 Task 5A 独立恢复：透明主体 matte

状态：`PASS（仅 Task 5A）`

本节追加记录改变技术路线后的独立子任务。交付范围只包含经过验证的透明主体、不可变源证据、可复现脚本与视觉 QA；没有创建、修改或声称完成 23 层、分组 PSD、seam 动画或 Task 5 的其余验收项。因此，上方对完整 Task 5 的 `BLOCKED` 结论并未被冒充为整体完成。

### 结论

- 最终文件：`assets/character/deepseek-v2/source/subject-rgba.png`
- 文件规格：`1024×1536 RGBA`
- 最终 SHA-256：`01519D11A7CC15BB23A2EF324CE27B8EDCC01C7DCB9F4BA62855E72E7D385A82`
- RGB 来源：最终 RGBA 的每个 RGB 像素都与只读工作区原图副本逐像素相等；模型和 alpha matting 只决定 alpha，没有重绘 RGB。
- 视觉结论：深色、浅色、棋盘三种背景以及耳朵/卷发、手指/披肩、裙边、白靴、尾巴/尾鳍五组 200% 局部图均已实际检查。气泡、声呐背景与靴底倒影已移除；关键白材质、卷发负空间、手指、双耳与两片尾鳍完整可用。

### 不可变源与模型证据

原始路径、工作区副本、字节数和尺寸保持不变：

- 原始路径：`E:/adventure/ai_code/codex_image/character/ai-anime-girl-deepseek-v2.png`
- 工作区副本：`assets/character/deepseek-v2/source/original.png`
- 原图与副本 SHA-256：`24DF7985AE880E21CB5EB7FF6C811631C00CEFC82F9BE4C91D580350C61A79D5`
- 字节数：`2082244`
- 尺寸/模式：`1024×1536 RGB`
- 结构化证据：`evidence/asset-source.json`

本次没有调用 built-in image generation、图像 CLI/API、在线 demo 或密钥服务，也没有上传原图。只从网络下载公开模型与 Python 依赖；源图推理完全在本机 CPU 执行。

- 模型：SkyTNT `anime-segmentation` 的 `isnetis.onnx`，以 rembg 的 `isnet-anime.onnx` 名称加载
- 上游仓库：`https://github.com/SkyTNT/anime-segmentation`
- 官方模型页：`https://huggingface.co/skytnt/anime-seg/blob/main/isnetis.onnx`
- 许可证：`Apache-2.0`
- 模型字节数：`176069933`
- SHA-256：`F15622D853E8260172812B657053460E20806F04B9E05147D49AF7BED31A6E99`
- MD5（同时匹配 rembg 发布记录）：`6F184E756BB3BD901C8849220A83E38E`
- 下载说明：官方 Hugging Face 直连在当前网络不可达，最终通过 `hf-mirror.com` 取得上游 blob；落盘后同时匹配官方 SHA-256 与 rembg MD5，不以镜像响应本身作为信任根。
- 本地模型位置：`C:/Users/UserX/AppData/Local/Temp/codex-task5a-isnet-anime/isnet-anime.onnx`，仅为临时运行依赖，未提交仓库。
- 运行时：Python `3.11.15`、`rembg 2.0.75`、`onnxruntime 1.29.0`、`CPUExecutionProvider`；最终记录的模型会话与推理耗时 `3.270 s`。

### 确定性构建路线

脚本 `scripts/build_character_matte.py` 执行以下有审计边界的本地流程：

1. 在解码前验证外部原图、工作区副本与 `evidence/asset-source.json` 的路径、字节数、尺寸和 SHA-256。
2. 在载入前同时验证 ONNX 的 SHA-256、MD5 与固定文件名，避免 rembg 静默改用或下载其他模型。
3. 强制 `CPUExecutionProvider` 运行 `isnet-anime`，取得 `1024×1536` 原始 alpha 预测。
4. 使用本地 closed-form alpha matting 做边缘细化：前景阈值 `235`、背景阈值 `5`、腐蚀核 `3`。
5. 在 alpha `16` 阈值保留最大主体连通域及 2 px 软边，移除分离气泡和声呐残留。
6. 使用未被 alpha matting 提升的原始 ISNet 主体作为引导，只在 `y≥1400` 清理靴底倒影，并保留 3 px 鞋底软边。
7. 把最终 alpha 附加到原图 RGB，落盘后再次逐像素验证 RGB 完全一致。

### 量化结果

完整机器可读记录：`evidence/assets/subject-matte-qa.json`。

| 指标 | 实测值 | 判读 |
| --- | ---: | --- |
| 非透明像素 | `493417` | 主体覆盖正常 |
| 全不透明 / 软 alpha 像素 | `441597 / 51820` | 保留抗锯齿、卷发与透明衣料边缘 |
| alpha≥128 主体像素 | `468033` | — |
| 最大连通主体占比（alpha≥128） | `0.9996346411` | 通过 `≥0.999` gate |
| alpha≥128 的小型分离像素 | `171` | 均为主轮廓软过渡后的发丝/高光小岛，200% 图未见独立背景物 |
| 内部透明洞 | `81` 个、`8005` px | 最大洞位于卷发之间；视觉核验为设计负空间，不在脸、手、披肩、裙、靴或尾鳍实体内部 |
| 移除的分离 matte 像素 | `3689` | 气泡/声呐背景残留 |
| 移除的地面倒影像素 | `8072` | 双靴实体保留 |
| `y≥1490` 非透明像素 | `0` | 地面反射 gate 通过 |
| 低 alpha 浅色风险像素（`0<alpha<32`） | `11672` | 对应等效全不透明面积 `487.2275 px` |
| 软边距主体轮廓距离 p50/p90/p95/p99/max | `2.0 / 5.6 / 7.7969 / 11.9969 / 19.3845 px` | 较宽处主要对应半透明卷发、发梢和衣料，而非连续背景白块 |

重点区域以 ISNet 原始高置信像素 `alpha≥240` 为参考、以最终 `alpha<128` 计损失：

| 区域 | 高置信参考像素 | 损失像素 | 损失率 |
| --- | ---: | ---: | ---: |
| 双耳与卷发 | `92584` | `276` | `0.2981%` |
| 手指与双手 | `167112` | `11` | `0.0066%` |
| 白披肩与裙 | `263754` | `15` | `0.0057%` |
| 双靴 | `55613` | `103` | `0.1852%` |
| 尾巴与尾鳍 | `121139` | `43` | `0.0355%` |

上述五区均通过 `≤0.5%` 的防误删 gate。靴区损失主要来自刻意清除的地面倒影边界；耳/卷发区还包含原始预测中的相邻浅背景。

### 200% 视觉 QA

全身背景图均为 `2048×3072`，使用 nearest-neighbor 放大以暴露真实像素边缘：

- `evidence/assets/matte-dark-200.png`
- `evidence/assets/matte-light-200.png`
- `evidence/assets/matte-checker-200.png`

重点局部：

- `evidence/assets/matte-detail-ears-curls-checker-200.png`
- `evidence/assets/matte-detail-hands-cape-checker-200.png`
- `evidence/assets/matte-detail-skirts-checker-200.png`
- `evidence/assets/matte-detail-boots-checker-200.png`
- `evidence/assets/matte-detail-tail-fins-checker-200.png`

原始预测和最终 alpha 也保留为审计图：

- `evidence/assets/matte-isnet-raw-mask.png`
- `evidence/assets/matte-final-alpha.png`

### 验证命令

```text
python -m unittest tests.python.test_build_character_matte -v
Ran 7 tests in 0.162s
OK
```

```text
python scripts/build_character_matte.py --model C:/Users/UserX/AppData/Local/Temp/codex-task5a-isnet-anime/isnet-anime.onnx
MATTE_VALIDATION=PASS
output=assets/character/deepseek-v2/source/subject-rgba.png
sha256=01519D11A7CC15BB23A2EF324CE27B8EDCC01C7DCB9F4BA62855E72E7D385A82
inferenceSeconds=3.27
```

```text
npm test -- tests/unit/character-types.test.ts
Test Files  1 passed (1)
Tests       2 passed (2)
```

```text
npm run typecheck
退出码 0
```

### 保留 concerns

- matte 达到当前 UI 合成可用质量，但不是人工逐像素绘制的影视级 rotoscope；在深色底 200% 下，少量极淡发梢、发卷和浅色衣缘仍可见约 1–2 px 的源图浅色 fringe。等效面积已量化为 `487.2275` 个全不透明像素，没有把它包装成“零 halo”。
- `81` 个内部透明洞是按阈值连通域统计，不代表 `81` 个缺陷；最大的洞均是卷发环之间的设计留白。若未来动画会大幅拉开头发层，仍应针对具体 layer seam 重新检查，而不能沿用本 matte 的静态结论。
- 本次只解除透明主体 matte 这一项阻塞。23 层、分组 PSD、层级 manifest 与六类 seam QA 仍属于后续 Task 5 工作，未在本提交中伪造。

---

## 2026-08-20 Task 5B：完整分层资产包

状态：`PASS（完整 Task 5）`

本节基于已过审的 `subject-rgba.png` 继续完成 Task 5B，并取代报告开头针对旧失败路线的整体 `BLOCKED` 结论。Task 5A 的 matte 事实与 concerns 仍保留，不被删除或改写。

### 最终交付

- `assets/character/deepseek-v2/layers/*.png`：严格 23 张、每张 `1024×1536 RGBA`，均有非空语义 alpha，文件哈希两两不同。
- `assets/character/deepseek-v2/source/deepseek-v2-layered.psd`：`9799750` bytes，可由 `psd-tools 1.18.0` 重新打开；顶层严格为 `back`、`body`、`head`、`face`、`front`、`props`、`effects` 七组，23 个命名像素层均位于指定组内。
- `assets/character/deepseek-v2/character.manifest.json`：schema `1`、画布 `1024×1536`、23 个唯一整数 zIndex、归一化 anchor、已知 motionGroup 与 `required=true`。
- `scripts/validate-character-assets.mjs`：fail-closed CLI validator。
- `evidence/assets/{neutral,blink,gaze-extremes,hair-offset,hand-offset,tail-offset}.png`：六类 full-size seam QA。
- `evidence/assets/movable-layer-preview.png`：`1920×1080` 用户预览 contact sheet。
- `evidence/assets/layer-stats.json`：逐层哈希、非透明像素、bbox、中性重合度与 seam 指标。

### 分层与补底方法

本阶段没有调用 built-in `image_gen`、图像 CLI/API、密钥服务或上传服务。输入只使用已批准且哈希固定的 `subject-rgba.png` 和不可变 `original.png`。构建脚本用人工校准多边形、颜色门限、连通域和保留源 alpha 的羽化完成语义分割；所有代码注释为中文。

遮挡恢复使用本地 OpenCV Telea inpainting，并只作用于显式遮挡区：脸底移除眼、眉、嘴和刘海遮挡；躯干补出前发和双手/前臂移动后暴露的衣料；尾巴层把误被复制到尾根的发梢替换为尾身底色。尾巴 QA 锁定裙摆遮挡下的根部，从 `y=980` 后平滑增加到 `8 px` 位移，避免原先根部上层与 warp 之间的裂缝。

中性合成相对已批准主体的实测结果：

| 指标 | 实测值 |
| --- | ---: |
| RGB mean absolute error | `0.207087` |
| RGB p95 absolute error | `0` |
| 主体覆盖率 | `1.0` |

23 层非透明像素从双眉的 `86/87 px` 到 torso 的 `285070 px` 不等；不存在空白层、整画布层或字节完全重复层。每层在 `alpha=0` 区域的 RGB 也被强制清零，防止把整张源图藏在透明像素中；23 张 PNG 合计 `1521163` bytes。完整逐层记录见 `layer-stats.json`。

### validator 失败契约

validator 会在成功前逐项验证 JSON/schema、固定画布、精确清单与顺序、路径不越界（含真实路径/链接检查）、文件存在、唯一整数 zIndex、anchor、motionGroup、`required=true`、PNG 结构、尺寸、显式 alpha、可解码的 8-bit 非隔行像素、非空 alpha、非整画布 alpha 与重复文件内容。

Vitest 真实负例覆盖并通过：

- 缺文件：`MISSING_FILE`
- 重复 zIndex：`DUPLICATE_Z_INDEX`
- 错误尺寸：`INVALID_DIMENSIONS`
- 无显式 alpha：`MISSING_ALPHA`
- anchor 越界：`INVALID_ANCHOR`
- 未知 motion group：`UNKNOWN_MOTION_GROUP`

### 六图逐张人工视觉 QA

以下六张均在最终全量重建后逐张使用 `view_image` 实际查看，不以脚本 PASS 代替视觉结论：

| 文件 | 具体视觉结论 |
| --- | --- |
| `neutral.png` | 双耳、卷发负空间、脸、双手、裙边、双靴、尾身与双尾鳍均完整；棋盘底未穿入实体，中性层对齐，无新透明洞或重复轮廓。 |
| `blink.png` | 两侧闭眼弧线落在原眼窝内，眼白/虹膜原位内容完全隐藏；脸底连续，没有眼洞、虹膜 ghost 或断裂眼线。 |
| `gaze-extremes.png` | 左右两端虹膜位移方向清楚，均被各自眼白 alpha 限制；两眼同步且没有原位虹膜残留、眼白破口或跨眼溢出。 |
| `hair-offset.png` | 刘海 `2 px`、后发 `4 px`、两侧卷发 `6 px` 分层错位可见；发根仍贴合头部，右侧披肩/尾根处旧 `204 px` 发梢 ghost 已消失，卷发之间仍保持真实透明负空间。 |
| `hand-offset.png` | 双手与前臂整体 `(+4,-3) px` 后，手指、袖口、发光 core 接触关系仍连贯；衣料补底覆盖原位置，没有手部 ghost、透明楔形洞或断肢。 |
| `tail-offset.png` | 尾根固定、尾身后段渐变到 `8 px`；裙摆下连接连续，修复前的深色纵向裂缝已消失，双尾鳍和外轮廓无断裂或明显色跳。 |

机器 seam 指标与人工结论一致：blink/gaze/hair/hand/tail 的 `transparentHolePixels=0`、`disconnectedRequiredParts=0`；hair/hand/tail 的 `originalPositionGhostPixels=0`。hair、hand、tail 的锚区搭接分别为 `7947`、`17362`、`10824 px`。

`movable-layer-preview.png` 也已用 `view_image` 检查：标题、六张卡片、动作标签、棋盘透明背景和人物缩略图均完整，无裁切、重叠或缺图。

### 最终验证

```text
node scripts/validate-character-assets.mjs
ASSET_VALIDATION=PASS LAYERS=23
```

```text
npm test
Test Files  5 passed (5)
Tests       45 passed (45)
```

```text
python -s -m unittest discover -s tests/python -v
Ran 13 tests
OK
```

```text
npm run typecheck
退出码 0
```

全量 Vitest 首次运行曾把 `tests/e2e/preview-smoke.spec.ts` 错当作单元测试并由 Playwright 拒绝。根因是 `vitest.config.ts` 未限定测试目录；现已最小化为只包含 `tests/unit/**/*.test.ts`，Playwright e2e 内容没有被删除或篡改。

### 保留 concerns

- 这是面向当前 UI 小幅 idle 动画的确定性分层，不是影视级逐帧 rotoscope。刘海 QA 刻意限制为 `2 px`；在 200% 近看，额头补底仍可能看到极轻微纹理差异。若未来要做大幅甩发、转头或超过当前位移的动作，应重新绘制隐藏面，不能外推本次 PASS。
- Task 5A 已记录的源 matte 约 `1–2 px` 浅色 fringe 仍是输入上限；本阶段没有把该既有边缘事实包装成零 halo。
- Python 图像构建依赖位于任务临时目录 `C:/Users/UserX/AppData/Local/Temp/codex-task5b-python`，使用 Python `3.11.15 -s`、OpenCV headless `4.12.0.88`、Pillow `12.3`、NumPy `2.2.6`、psd-tools `1.18.0`。已提交构建脚本和统计结果，但没有把这些临时 wheel/vendor 文件写入仓库。
