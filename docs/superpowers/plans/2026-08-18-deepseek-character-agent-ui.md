# DeepSeek Character Agent UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an upgrade-safe DeepSeek Harness character interface whose short-term layered PNG avatar reacts to real Agent state and can later be replaced by Live2D without changing application behavior.

**Architecture:** Keep all source in an independent TypeScript workspace. A stable `HarnessBridge` feeds a renderer-independent `CharacterController`; React UI components consume controller snapshots, while either `LayeredPngRenderer` or `Live2DRenderer` renders the character. Installation into Harness is performed by a version-gated, backup-first patcher with a verified rollback path.

**Tech Stack:** Node.js 22.23.2, TypeScript 6.0.3, React 18.3.1, Vite 6, Vitest 4.1.8, Playwright 1.49, PNG/PSD assets, optional Live2D Cubism Editor and Cubism SDK for Web.

**Spec:** `docs/superpowers/specs/2026-08-18-deepseek-character-agent-ui-design.md`

## Global Constraints

- All code comments must be written in Chinese.
- The original `ai-anime-girl-deepseek-v2.png` must never be overwritten.
- Short replies contain one sentence for simple results and at most three short items for complex results.
- Desktop shows no more than 4 to 6 task bubbles; narrow layouts show fewer and always preserve the `…` entry when overflow exists.
- Sleep starts after a randomized 150 to 210 seconds without real input; mouse movement alone never wakes the character.
- `prefers-reduced-motion` and explicit `off`, `gentle`, and `full` motion settings are mandatory.
- Harness 0.1.0-rc.6 is the initial compatibility target; unknown versions must fail closed and leave the native UI usable.
- No purchase, subscription, license acceptance, upload to an external service, or outsourcing may occur without explicit user approval of the amount and purpose.
- Never claim completion without real browser E2E, restart, uninstall, and rollback evidence.

## Scope Decomposition

This plan is an executable roadmap with four review gates. Gate A produces a standalone character runtime; Gate B produces validated character assets and the layered renderer; Gate C produces the complete standalone persona UI; Gate D integrates and verifies it in Harness. The later Live2D replacement starts only after the layered PNG MVP passes Gate D.

## File Structure

```text
dsher/
├─ package.json                         # workspace scripts and pinned tools
├─ tsconfig.json                        # shared strict TypeScript settings
├─ vite.config.ts                       # standalone preview and production build
├─ vitest.config.ts                     # unit and component test configuration
├─ playwright.config.ts                 # browser E2E configuration
├─ src/
│  ├─ character/
│  │  ├─ types.ts                       # public state, action, renderer contracts
│  │  ├─ character-controller.ts        # state priority and transitions
│  │  ├─ idle-action-scheduler.ts       # weighted idle actions and sleeping
│  │  ├─ gaze-controller.ts             # bounded, smoothed gaze target
│  │  ├─ motion-coordinator.ts           # combines body, face, prop and camera motion
│  │  ├─ asset-manifest.ts              # manifest schema and validation
│  │  ├─ layered-png-renderer.tsx        # short-term layered renderer
│  │  └─ live2d-renderer.ts              # later Cubism adapter
│  ├─ harness/
│  │  ├─ harness-bridge.ts               # stable app-facing Harness contract
│  │  ├─ rc6-adapter.ts                  # 0.1.0-rc.6 event/state adapter
│  │  └─ native-fallback.ts              # safe disable/fallback behavior
│  ├─ ui/
│  │  ├─ character-stage.tsx             # main stage and adaptive framing
│  │  ├─ task-bubbles.tsx                 # visible tasks, plus, overflow browser
│  │  ├─ speech-bubble.tsx                # concise response surface
│  │  ├─ focus-reader.tsx                 # complete Markdown/tool output
│  │  ├─ persona-composer.tsx             # long rectangular input surface
│  │  ├─ top-bar.tsx                      # user/settings/model/permission entries
│  │  └─ persona-shell.tsx                # composition and focus management
│  ├─ styles/tokens.css                   # deep-sea-lab design tokens
│  └─ preview/main.tsx                    # standalone deterministic preview
├─ assets/character/deepseek-v2/
│  ├─ source/                             # immutable source and layered PSD
│  ├─ layers/                             # exported transparent parts
│  └─ character.manifest.json             # z-order, anchors, bounds and groups
├─ scripts/
│  ├─ inspect-harness-rc6.mjs             # compatibility evidence collector
│  ├─ validate-character-assets.mjs        # dimensions, alpha, manifest validation
│  ├─ install-harness-mod.ps1              # version-gated backup-first installer
│  └─ uninstall-harness-mod.ps1            # verified restoration
├─ tests/unit/                             # Vitest behavior tests
├─ tests/e2e/                              # Playwright standalone and Harness E2E
└─ evidence/                               # generated JSON reports and screenshots
```

---

### Task 1: Bootstrap the Independent Workspace

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `vitest.config.ts`
- Create: `playwright.config.ts`
- Create: `.gitignore`
- Create: `src/preview/main.tsx`

**Interfaces:**
- Consumes: Node.js 22.23.2.
- Produces: `npm run typecheck`, `npm test`, `npm run build`, and `npm run test:e2e`.

- [ ] **Step 1: Initialize version control and ignore generated/private artifacts**

```powershell
git init
```

Create `.gitignore` with:

```gitignore
node_modules/
dist/
coverage/
test-results/
playwright-report/
.superpowers/
evidence/runtime/
assets/character/deepseek-v2/source/*.psd~
```

- [ ] **Step 2: Create the pinned package definition**

```json
{
  "name": "deepseek-character-agent-ui",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@playwright/test": "1.49.0",
    "@types/node": "22.10.2",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "@vitejs/plugin-react": "4.3.4",
    "typescript": "6.0.3",
    "vite": "6.0.11",
    "vitest": "4.1.8"
  }
}
```

- [ ] **Step 3: Install with the verified portable runtime**

Run:

```powershell
& 'E:\Apps\DeepSeekHarness\runtime\node-v22.23.2-win-x64\node.exe' 'E:\Apps\DeepSeekHarness\runtime\node-v22.23.2-win-x64\node_modules\npm\bin\npm-cli.js' install
```

Expected: `package-lock.json` is created and `npm ls --depth=0` exits 0.

- [ ] **Step 4: Add strict TypeScript and a minimal React preview**

Use `strict: true`, `noUncheckedIndexedAccess: true`, `jsx: "react-jsx"`, and `moduleResolution: "Bundler"`. Render `<main data-testid="preview-root">DeepSeek Character UI</main>` from `src/preview/main.tsx`.

- [ ] **Step 5: Verify and commit**

```powershell
npm run typecheck
npm test -- --passWithNoTests
npm run build
git add .gitignore package.json package-lock.json tsconfig.json vite.config.ts vitest.config.ts playwright.config.ts src/preview/main.tsx
git commit -m "build: initialize character ui workspace"
```

Expected: all commands exit 0 and the commit contains no Harness installation files.

### Task 2: Define Character Runtime Contracts

**Files:**
- Create: `src/character/types.ts`
- Create: `tests/unit/character-types.test.ts`

**Interfaces:**
- Consumes: none.
- Produces: `CharacterState`, `CharacterEvent`, `CharacterSnapshot`, `CharacterRenderer`, and `MotionCommand`.

- [ ] **Step 1: Write the contract test**

```ts
import { describe, expect, test } from 'vitest';
import { CHARACTER_STATES, isCharacterState } from '../../src/character/types';

describe('character state contract', () => {
  test('contains every approved state', () => {
    expect(CHARACTER_STATES).toEqual([
      'idle', 'user_input', 'thinking', 'streaming', 'tool_running',
      'waiting_user', 'success', 'error', 'sleeping', 'waking',
    ]);
  });

  test('rejects unknown state names', () => {
    expect(isCharacterState('dancing')).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test and verify failure**

Run: `npm test -- tests/unit/character-types.test.ts`

Expected: FAIL because `src/character/types.ts` does not exist.

- [ ] **Step 3: Implement the public contracts**

```ts
export const CHARACTER_STATES = [
  'idle', 'user_input', 'thinking', 'streaming', 'tool_running',
  'waiting_user', 'success', 'error', 'sleeping', 'waking',
] as const;

export type CharacterState = typeof CHARACTER_STATES[number];
export type MotionLevel = 'off' | 'gentle' | 'full';

export type CharacterEvent =
  | { type: 'agent-state'; state: Exclude<CharacterState, 'sleeping' | 'waking'>; at: number }
  | { type: 'real-input'; at: number }
  | { type: 'idle-timeout'; at: number }
  | { type: 'motion-finished'; motionId: string; at: number };

export interface CharacterSnapshot {
  state: CharacterState;
  previousState: CharacterState | null;
  enteredAt: number;
  motionLevel: MotionLevel;
}

export interface MotionCommand {
  id: string;
  channel: 'body' | 'face' | 'gaze' | 'prop' | 'camera';
  name: string;
  priority: number;
  durationMs: number;
}

export interface CharacterRenderer {
  mount(target: HTMLElement): Promise<void>;
  apply(snapshot: CharacterSnapshot, commands: readonly MotionCommand[]): void;
  setGaze(x: number, y: number): void;
  dispose(): void;
}

export const isCharacterState = (value: string): value is CharacterState =>
  (CHARACTER_STATES as readonly string[]).includes(value);
```

- [ ] **Step 4: Verify and commit**

```powershell
npm test -- tests/unit/character-types.test.ts
npm run typecheck
git add src/character/types.ts tests/unit/character-types.test.ts
git commit -m "feat: define character runtime contracts"
```

### Task 3: Implement State Priority and Wake/Sleep Transitions

**Files:**
- Create: `src/character/character-controller.ts`
- Create: `tests/unit/character-controller.test.ts`

**Interfaces:**
- Consumes: `CharacterEvent`, `CharacterSnapshot` from Task 2.
- Produces: `CharacterController.dispatch(event): CharacterSnapshot` and `getSnapshot()`.

- [ ] **Step 1: Write failing transition tests**

```ts
import { describe, expect, test } from 'vitest';
import { CharacterController } from '../../src/character/character-controller';

describe('CharacterController', () => {
  test('real input wakes a sleeping character', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'idle-timeout', at: 180_000 });
    expect(controller.getSnapshot().state).toBe('sleeping');
    controller.dispatch({ type: 'real-input', at: 180_100 });
    expect(controller.getSnapshot().state).toBe('waking');
  });

  test('thinking interrupts an idle motion', () => {
    const controller = new CharacterController(0);
    controller.dispatch({ type: 'agent-state', state: 'thinking', at: 50 });
    expect(controller.getSnapshot().state).toBe('thinking');
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run: `npm test -- tests/unit/character-controller.test.ts`

Expected: FAIL because `CharacterController` is missing.

- [ ] **Step 3: Implement a pure reducer-backed controller**

Implement constructor `CharacterController(now: number, motionLevel: MotionLevel = 'full')`, immutable snapshots, `dispatch`, and `getSnapshot`. `real-input` maps `sleeping -> waking`; `motion-finished` maps `waking -> user_input`; all `agent-state` events immediately replace cosmetic idle states.

- [ ] **Step 4: Add stale-event protection**

Add a test where an event with `at < enteredAt` is ignored, then implement the guard. This prevents delayed Harness events from resurrecting old states.

- [ ] **Step 5: Verify and commit**

```powershell
npm test -- tests/unit/character-controller.test.ts
npm run typecheck
git add src/character/character-controller.ts tests/unit/character-controller.test.ts
git commit -m "feat: add character state controller"
```

### Task 4: Add Deterministic Idle Actions, Sleep, and Gaze

**Files:**
- Create: `src/character/idle-action-scheduler.ts`
- Create: `src/character/gaze-controller.ts`
- Create: `src/character/motion-coordinator.ts`
- Create: `tests/unit/idle-action-scheduler.test.ts`
- Create: `tests/unit/gaze-controller.test.ts`

**Interfaces:**
- Consumes: `CharacterSnapshot`, `MotionCommand`.
- Produces: `IdleActionScheduler.tick(now)`, `GazeController.update(target, deltaMs)`, and `MotionCoordinator.resolve(commands)`.

- [ ] **Step 1: Test deterministic sleep bounds and no immediate repeats**

Inject `random: () => number` and a clock. Assert random `0` schedules sleep at 150,000 ms, random `1` schedules at 210,000 ms, and two successive special actions never share the same name.

- [ ] **Step 2: Implement the scheduler**

Use approved actions `blink`, `look-away`, `adjust-stance`, `touch-hair`, and `tail-sway`. Only emit special actions for `idle`; clear them immediately on any non-idle snapshot. Do not wake on pointer events.

- [ ] **Step 3: Test and implement bounded gaze smoothing**

Test that an extreme pointer target clamps to `x=-1..1`, `y=-1..1`, and that a 16 ms update moves less than 25% of the remaining distance. Use exponential smoothing so behavior is frame-rate independent.

- [ ] **Step 4: Test and implement motion channel arbitration**

For commands on the same channel, keep the highest priority; for equal priority, keep the newest command. Allow body, face, gaze, prop, and camera commands to run together.

- [ ] **Step 5: Verify and commit**

```powershell
npm test -- tests/unit/idle-action-scheduler.test.ts tests/unit/gaze-controller.test.ts
npm run typecheck
git add src/character/idle-action-scheduler.ts src/character/gaze-controller.ts src/character/motion-coordinator.ts tests/unit
git commit -m "feat: add idle motion and gaze controls"
```

**Gate A acceptance:** Unit tests cover all ten character states, stale events, deterministic sleep boundaries, input wake, pointer non-wake, gaze clamping, and motion priority.

### Task 5: Produce and Validate the Character Asset Package

**Files:**
- Copy: `E:/adventure/ai_code/codex_image/character/ai-anime-girl-deepseek-v2.png` -> `assets/character/deepseek-v2/source/original.png`
- Create: `assets/character/deepseek-v2/source/deepseek-v2-layered.psd`
- Create: `assets/character/deepseek-v2/character.manifest.json`
- Create: `scripts/validate-character-assets.mjs`
- Create: `tests/unit/asset-manifest.test.ts`

**Interfaces:**
- Consumes: immutable 1024x1536 source PNG.
- Produces: validated transparent layers and `CharacterAssetManifest`.

- [ ] **Step 1: Record source integrity**

Copy the source, calculate SHA-256 for both files, and save the matching hash in `evidence/asset-source.json`. Stop if hashes differ.

- [ ] **Step 2: Create the exact layer inventory**

The PSD must contain named groups `back`, `body`, `head`, `face`, `front`, `props`, and `effects`. Required exported layers are `back-hair`, `tail`, `torso`, `head-base`, `eye-left-white`, `eye-left-iris`, `eye-left-upper-lid`, `eye-right-white`, `eye-right-iris`, `eye-right-upper-lid`, `brow-left`, `brow-right`, `mouth-neutral`, `mouth-smile`, `mouth-talk`, `mouth-worried`, `front-hair`, `side-hair-left`, `side-hair-right`, `hand-front`, `core`, `bubbles`, and `sonar`.

- [ ] **Step 3: Separate and repair materials**

Use local tools first. AI masks may initialize selections, but manually repair the face, both eyes, both hands, curls, garment edges, and tail attachment at 200% zoom. Fill every newly exposed region under hair, hands, arms, and tail. Export each layer as a transparent PNG without resizing the 1024x1536 canvas.

- [ ] **Step 4: Define the manifest**

Create `character.manifest.json` with schema version `1`, canvas `{ "width": 1024, "height": 1536 }`, explicit integer `zIndex`, normalized anchors, motion group, required flag, and file path for every required layer.

- [ ] **Step 5: Implement and run validation**

The validator must reject missing files, duplicate z-indices, dimensions other than 1024x1536, images without alpha, anchors outside `0..1`, and unknown motion groups. Run `node scripts/validate-character-assets.mjs` and expect `ASSET_VALIDATION=PASS`.

- [ ] **Step 6: Perform visual seam QA and commit**

Render neutral, blink, gaze extremes, hair offset, hand offset, and tail offset to `evidence/assets/*.png`. Inspect at full size; reject transparent holes, original-position ghosts, broken line art, color jumps, or disconnected anatomy.

```powershell
git add assets/character/deepseek-v2 scripts/validate-character-assets.mjs tests/unit/asset-manifest.test.ts evidence/asset-source.json evidence/assets
git commit -m "feat: add validated layered character assets"
```

### Task 6: Implement the Layered PNG Renderer

**Files:**
- Create: `src/character/asset-manifest.ts`
- Create: `src/character/layered-png-renderer.tsx`
- Create: `tests/unit/layered-png-renderer.test.tsx`
- Modify: `src/preview/main.tsx`

**Interfaces:**
- Consumes: `CharacterRenderer`, `CharacterSnapshot`, `MotionCommand`, and `character.manifest.json`.
- Produces: mountable layered renderer with named channels and reduced-motion fallback.

- [ ] **Step 1: Add React component test dependencies**

Install exact versions `@testing-library/react@16.1.0`, `@testing-library/jest-dom@6.6.3`, and `jsdom@25.0.1` as dev dependencies.

- [ ] **Step 2: Write failing render tests**

Assert every required layer renders in z-order, `sleeping` closes both eyelids, `streaming` selects `mouth-talk`, and motion level `off` removes continuous animation attributes.

- [ ] **Step 3: Implement manifest parsing and layer composition**

Render one absolutely positioned `<img>` per manifest layer inside a 1024x1536 logical stage. Use CSS custom properties only for renderer parameters such as eye x/y, breath, head angle, hair lag, tail lag, and camera scale.

- [ ] **Step 4: Implement renderer commands**

Map approved motion names to bounded parameter targets. Use `requestAnimationFrame`, frame-independent smoothing, and a single loop. Pause the loop when `document.visibilityState === 'hidden'`.

- [ ] **Step 5: Verify preview and commit**

Run unit tests, build, and manually trigger every state from deterministic preview controls. Capture `evidence/renderer/state-*.png`.

```powershell
git add src/character src/preview tests/unit evidence/renderer package.json package-lock.json
git commit -m "feat: render layered DeepSeek character"
```

**Gate B acceptance:** Asset validation passes, six seam QA poses are clean, all state render tests pass, hidden tabs pause animation, and reduced-motion mode remains informative.

### Task 7: Build the Persona UI Shell

**Files:**
- Create: `src/ui/character-stage.tsx`
- Create: `src/ui/task-bubbles.tsx`
- Create: `src/ui/speech-bubble.tsx`
- Create: `src/ui/focus-reader.tsx`
- Create: `src/ui/persona-composer.tsx`
- Create: `src/ui/top-bar.tsx`
- Create: `src/ui/persona-shell.tsx`
- Create: `src/styles/tokens.css`
- Create: `tests/unit/persona-shell.test.tsx`

**Interfaces:**
- Consumes: `CharacterController`, `CharacterRenderer`, and `HarnessBridge`.
- Produces: `PersonaShell` with task navigation, input, concise reply, and full reader.

- [ ] **Step 1: Define the stable Harness bridge**

```ts
export interface HarnessTask { id: string; title: string; projectTitle?: string }
export interface HarnessReply { id: string; concise: string; fullMarkdown: string; status: 'streaming' | 'complete' | 'error' }
export type HarnessBridgeEvent =
  | { type: 'tasks-changed'; tasks: readonly HarnessTask[] }
  | { type: 'active-task-changed'; taskId: string | null }
  | { type: 'agent-state'; state: 'idle' | 'thinking' | 'streaming' | 'tool_running' | 'waiting_user' | 'success' | 'error'; at: number }
  | { type: 'reply-changed'; reply: HarnessReply }
  | { type: 'bridge-error'; message: string; recoverable: boolean };
export interface HarnessBridge {
  getTasks(): readonly HarnessTask[];
  getActiveTaskId(): string | null;
  createTask(): Promise<string>;
  openTask(id: string): Promise<void>;
  submit(text: string): Promise<void>;
  subscribe(listener: (event: HarnessBridgeEvent) => void): () => void;
}
```

- [ ] **Step 2: Write task bubble behavior tests**

Test at 1440 px that five recent tasks plus `+` are visible and overflow creates `…`; at 390 px test two recent tasks plus `+` and `…`. Test selection calls `openTask(id)` and plus calls `createTask()`.

- [ ] **Step 3: Implement deep-sea-lab tokens and adaptive stage**

Use sea-salt surfaces, deep blue text, cyan accents, and limited purple glow. Keep character stage at 65% to 72% available height and composer at the bottom with 16 to 20 px radius.

- [ ] **Step 4: Test and implement concise/full reply behavior**

One-sentence replies render directly; complex concise replies render at most three items. Clicking opens `FocusReader`; reader shows exact `fullMarkdown`, traps focus, marks the background inert, and restores focus to the bubble on close.

- [ ] **Step 5: Test and implement real-input wake**

Dispatch `real-input` only from `beforeinput` or an actual value-changing input event. `pointermove`, hover, focus alone, and task switching must not wake a sleeping character.

- [ ] **Step 6: Verify and commit**

```powershell
npm test -- tests/unit/persona-shell.test.tsx
npm run build
git add src/ui src/styles src/harness/harness-bridge.ts tests/unit
git commit -m "feat: add persona interface shell"
```

### Task 8: Add Standalone Browser E2E

**Files:**
- Create: `tests/e2e/persona-states.spec.ts`
- Create: `tests/e2e/persona-navigation.spec.ts`
- Create: `tests/e2e/persona-responsive.spec.ts`
- Modify: `src/preview/main.tsx`

**Interfaces:**
- Consumes: `PersonaShell` and a deterministic `FakeHarnessBridge`.
- Produces: screenshots and JSON evidence for all approved states and widths.

- [ ] **Step 1: Add deterministic preview fixtures**

Support URL parameters `state`, `widthPreset`, `motion`, and `taskCount`. Seed random scheduling so screenshots are reproducible.

- [ ] **Step 2: Test the complete state path**

Drive `idle -> user_input -> thinking -> streaming -> tool_running -> success -> idle`, then fake 180 seconds and verify `sleeping -> waking -> user_input` after typing.

- [ ] **Step 3: Test navigation and focus**

Verify plus creates a task, visible bubbles switch tasks, ellipsis finds an overflow task, focus reader traps and restores focus, and background controls cannot be activated while inert.

- [ ] **Step 4: Test 1440, 1024, and 390 px layouts**

Capture screenshots and assert no horizontal overflow, no overlap with face safe area, and composer/send controls remain visible.

- [ ] **Step 5: Commit Gate C evidence**

```powershell
npm run test:e2e
git add tests/e2e src/preview evidence/e2e
git commit -m "test: verify standalone persona ui"
```

**Gate C acceptance:** Standalone E2E passes at all three widths, state transitions are real fixture events rather than timers, and console error report is empty.

### Task 9: Inspect and Freeze the Harness 0.1.0-rc.6 Integration Surface

**Files:**
- Create: `scripts/inspect-harness-rc6.mjs`
- Create: `evidence/harness/rc6-surface.json`
- Create: `tests/unit/harness-version.test.ts`

**Interfaces:**
- Consumes: installed packages under `E:/Apps/DeepSeekHarness/node_modules/@deepseek-ai`.
- Produces: exact package hashes, exported types, slot identifiers, frontend entry files, and a compatibility predicate.

- [ ] **Step 1: Write the version guard test**

Assert `isSupportedHarnessVersion('0.1.0-rc.6') === true` and `isSupportedHarnessVersion('0.1.0-rc.7') === false` until separately certified.

- [ ] **Step 2: Implement the read-only inspector**

Collect package versions and SHA-256 for `dsh-web-app`, `dsh-web-frontend`, `dsh-client-ui-conversation`, `dsh-client-ui-sidebar`, `dsh-client-ui-theme`, and `dsh-client-ui-slots`. Record `index.html` asset references and exported `.d.ts` symbols. Never modify the installation.

- [ ] **Step 3: Run and review evidence**

Run `node scripts/inspect-harness-rc6.mjs E:\Apps\DeepSeekHarness`. Expected: `HARNESS_INSPECTION=PASS`, version `0.1.0-rc.6`, and all six packages present.

- [ ] **Step 4: Choose the least invasive certified hook**

Prefer a published Cordis/UI slot if the evidence contains a mount point that can replace the shell without editing compiled package code. Otherwise certify the exact `index.html` plus frontend bundle hashes required by the patch installer. Record the chosen mode as either `plugin` or `versioned-patch` in `rc6-surface.json`; no third value is allowed.

- [ ] **Step 5: Commit**

```powershell
git add scripts/inspect-harness-rc6.mjs evidence/harness/rc6-surface.json tests/unit/harness-version.test.ts
git commit -m "test: freeze harness rc6 integration surface"
```

### Task 10: Implement the Harness Adapter and Native Fallback

**Files:**
- Create: `src/harness/rc6-adapter.ts`
- Create: `src/harness/native-fallback.ts`
- Create: `tests/unit/rc6-adapter.test.ts`

**Interfaces:**
- Consumes: certified hooks in `evidence/harness/rc6-surface.json`.
- Produces: `createRc6HarnessBridge(runtime): HarnessBridge` and `activateNativeFallback(reason)`.

- [ ] **Step 1: Write fixture-driven adapter tests**

Use captured rc6 event fixtures for task list, active task, user submit, thinking, streaming chunks, tool start/end, waiting user, success, and error. Assert the adapter emits stable `HarnessBridgeEvent` objects and preserves the complete Markdown output.

- [ ] **Step 2: Implement task and submit mapping**

Map rc6 session/workspace records to `HarnessTask`, call the certified new/open/submit functions, and never infer success from elapsed time.

- [ ] **Step 3: Implement state and reply mapping**

Aggregate streaming content without truncating full output. Emit `streaming`, `tool_running`, `waiting_user`, `success`, and `error` from real rc6 events.

- [ ] **Step 4: Implement fail-closed fallback**

On version mismatch, missing hook, invalid event, or renderer startup failure, disable the persona mount, restore native shell visibility, record the reason, and keep Harness input usable.

- [ ] **Step 5: Verify and commit**

```powershell
npm test -- tests/unit/rc6-adapter.test.ts tests/unit/harness-version.test.ts
git add src/harness tests/unit/rc6-adapter.test.ts
git commit -m "feat: bridge harness rc6 to persona ui"
```

### Task 11: Build Backup-First Install and Uninstall Scripts

**Files:**
- Create: `scripts/install-harness-mod.ps1`
- Create: `scripts/uninstall-harness-mod.ps1`
- Create: `tests/e2e/install-rollback.Tests.ps1`

**Interfaces:**
- Consumes: production build and `rc6-surface.json`.
- Produces: idempotent install, manifest, backup, uninstall, and rollback.

- [ ] **Step 1: Write Pester tests against a temporary fixture**

Test unsupported version rejection, hash mismatch rejection, backup creation, second-install idempotence, uninstall restoration, and restoration after a simulated failed copy.

- [ ] **Step 2: Implement installer preflight**

Resolve and verify the explicit `E:\Apps\DeepSeekHarness` target, version, hashes, free space, build output, and writable backup directory. Never use recursive deletion, globs, `$HOME`, or unresolved targets.

- [ ] **Step 3: Implement atomic installation**

Copy certified targets to a timestamped backup, write new assets to temporary sibling paths, verify hashes, then rename into place. Persist `install-manifest.json` with original and installed hashes.

- [ ] **Step 4: Implement uninstall and automatic rollback**

Restore only files named in the manifest. Verify restored hashes before reporting success. If any install step fails, invoke the same restoration routine automatically.

- [ ] **Step 5: Test and commit**

```powershell
Invoke-Pester tests/e2e/install-rollback.Tests.ps1
git add scripts/install-harness-mod.ps1 scripts/uninstall-harness-mod.ps1 tests/e2e/install-rollback.Tests.ps1
git commit -m "feat: add safe harness mod installer"
```

### Task 12: Run Real Harness E2E and Restart Validation

**Files:**
- Create: `tests/e2e/harness-real.spec.ts`
- Create: `evidence/harness/report.json`
- Create: `evidence/harness/console-errors.json`
- Create: `evidence/harness/state-errors.json`
- Create: `evidence/harness/restart.json`

**Interfaces:**
- Consumes: installed rc6 integration.
- Produces: final Gate D acceptance evidence.

- [ ] **Step 1: Install and launch on a non-default test port**

Run the installer, start Harness on port 3081 with the existing persistent data isolated from test data, and verify HTTP 200 before browser testing.

- [ ] **Step 2: Exercise real tasks**

Create a task, type a message, observe real `user_input -> thinking -> streaming -> success -> idle`, run one safe read-only tool to observe `tool_running`, open full output, switch tasks, use overflow search, and return to the original task.

- [ ] **Step 3: Validate sleep and wake**

Use an injected test clock only for the UI idle scheduler, confirm sleep within the configured 150 to 210 second bound, confirm mouse movement does not wake, then type and confirm immediate `waking` without lost input.

- [ ] **Step 4: Validate responsive, accessibility, and performance behavior**

Capture 1440, 1024, and 390 px screenshots; exercise keyboard-only navigation; run reduced-motion mode; record animation frame samples and require median frame rate at least 55 FPS on the current laptop or document the 30 FPS degraded mode trigger.

- [ ] **Step 5: Restart, uninstall, and restore**

Stop Harness, start it again, verify settings and tasks persist, uninstall the mod, verify native UI returns, reinstall, and repeat the HTTP/browser smoke test.

- [ ] **Step 6: Commit evidence**

```powershell
npm run test:e2e -- tests/e2e/harness-real.spec.ts
git add tests/e2e/harness-real.spec.ts evidence/harness
git commit -m "test: verify persona ui in real harness"
```

**Gate D acceptance:** HTTP and browser tests pass after restart, state and console error reports are empty, task data persists, uninstall restores the native UI, and reinstall succeeds from the saved manifest.

### Task 13: Replace the Short-Term Renderer with Live2D

**Files:**
- Create: `assets/character/deepseek-v2/live2d/`
- Create: `src/character/live2d-renderer.ts`
- Create: `tests/unit/live2d-renderer.test.ts`
- Create: `tests/e2e/live2d-parity.spec.ts`

**Interfaces:**
- Consumes: approved layered PSD, `CharacterRenderer`, and existing motion commands.
- Produces: `Live2DRenderer` with behavior parity and improved deformation.

- [ ] **Step 1: Present the paid-tool decision before acquisition**

Provide the current Cubism Editor plan, SDK release-license implications for private versus distributed use, any Photoshop/plugin cost, and professional rigger quote if proposed. Continue only after explicit user approval.

- [ ] **Step 2: Import and rig the approved PSD**

Create ArtMesh and deformers for head angle, body angle, eyes, brows, eyelids, mouth, breathing, hair, cape, skirt, hands, core, and tail. Configure physics for hair, cape, skirt, and tail. Export `.moc3`, `.model3.json`, motions, expressions, pose, physics, and textures.

- [ ] **Step 3: Write renderer parity tests**

Use a fake Cubism model to assert every `CharacterState` and every approved `MotionCommand` maps to defined parameters or motions, disposal releases WebGL resources, and reduced-motion disables continuous physics while retaining expressions.

- [ ] **Step 4: Implement `Live2DRenderer`**

Implement the same `mount`, `apply`, `setGaze`, and `dispose` interface. Do not expose Cubism-specific objects outside the renderer.

- [ ] **Step 5: Run visual parity and quality E2E**

Replay the Gate C and Gate D state paths, compare functional assertions, and add close-up QA for head turn, blink, gaze extremes, mouth, hand motion, hair, and tail physics.

- [ ] **Step 6: Commit the renderer swap**

```powershell
git add assets/character/deepseek-v2/live2d src/character/live2d-renderer.ts tests/unit/live2d-renderer.test.ts tests/e2e/live2d-parity.spec.ts evidence/live2d
git commit -m "feat: upgrade character renderer to live2d"
```

**Live2D acceptance:** All Gate C and Gate D behavior tests pass unchanged, no anatomy seams or physics explosions occur, private-use licensing is recorded, and the layered PNG renderer remains available as fallback.

## Final Verification

- [ ] Run `npm run typecheck` and expect exit 0.
- [ ] Run `npm test` and expect all unit/component tests to pass.
- [ ] Run `npm run build` and expect a production bundle with no TypeScript errors.
- [ ] Run `npm run test:e2e` and expect standalone and real-Harness suites to pass.
- [ ] Confirm `evidence/harness/console-errors.json` and `evidence/harness/state-errors.json` contain empty arrays.
- [ ] Confirm original character SHA-256 still matches `evidence/asset-source.json`.
- [ ] Confirm uninstall restores every original Harness hash.
- [ ] Confirm `git status --short` contains no untracked evidence, temporary assets, installation files, credentials, or unrelated user files.
