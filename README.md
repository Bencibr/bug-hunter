# Bug-Hunter Agent

永无止境地挖掘错误的对抗性审计 Agent。白盒源码审计 + 黑盒成品测试
（CLI / PTY / 数据接口 / **UI 视觉交互面**），多轮循环机制：每轮消耗
1 点寿命做一轮全量发现，找到真实错误 +1，欺诈 -1，寿命归 0 即死亡。

---

## 机制一览

- **多轮循环**：`life > 0` 就自动进入下一轮，直到寿命耗尽死亡。
- **寿命记账**：`verify_life.py` 是外部权威校验器，防止 agent 自评舞弊
  （篡改寿命、伪造证据、绕过结算都会被 diff 拦截并回滚）。
- **错题集**：`mistake-book.md` 沉淀历轮 bug 的「分类 + 根因 + 同类排查点」，
  每轮勘察优先通读，把历史教训变成主动排查清单。
- **UI 挖 bug**：通过 Playwright 打开网页，多断点截图 + DOM 几何断言 +
  交互轰炸 + 状态覆盖，找布局崩塌、焦点陷阱、文案截断、对比度不足等视觉 bug。

### 文件结构

| 文件 | 作用 |
|------|------|
| `.opencode/agent/bug-hunter.md` | Agent 定义（核心提示词 + 生命周期规则） |
| `.opencode/agent/verify_life.py` | 寿命校验器（check/settle/snapshot/diff/restore） |
| `.opencode/agent/launch_bug_hunter.py` | 启动协议（pre/post/status） |
| `.opencode/agent/lockdown.sh` | OS 层加固（把校验器/基线设为只读） |
| `.opencode/agent/mistake-book.md` | 错题集（反思归类复用） |
| `.opencode/agent/bug-hunter-life.json` | 寿命状态（运行时生成，不入库） |
| `.opencode/agent/findings_round*.txt` | 每轮发现记录 |
| `opencode.json` | Playwright MCP 配置（UI 挖 bug 用） |

> 提示：`bug-hunter-life.json` 和 `.snapshot` 已被 `.gitignore` 排除。
> 每个使用者 clone 后从初始态（life=1）各自开始，历史发现不共享。

---

## 前置要求

- **Python 3**：运行 `verify_life.py` / `launch_bug_hunter.py`
- **Node.js + npx**：运行 Playwright MCP（UI 挖 bug 才需要）
- **AI 编程工具**：任选一款支持 agent/skill 的（见下文）

---

## 各工具安装与使用

### 1. OpenCode（原生支持，推荐）

本项目已内置 `.opencode/agent/bug-hunter.md` 和 `opencode.json`，clone 后即用。

```bash
git clone https://gitea.sp.dev/AI/bug-hunter.git
cd bug-hunter
```

**启动协议**（校验基线 → 快照 → 启动 → 结束后核对）：

```bash
python3 .opencode/agent/launch_bug_hunter.py pre
```

然后在 opencode 中通过 **Task 工具**调用 subagent，或输入框 `@` 提及：

```
@bug-hunter 开始挖掘
```

运行结束后核对：

```bash
python3 .opencode/agent/launch_bug_hunter.py post
```

> OpenCode 原生支持本仓库 frontmatter 的 `mode: all`、`permission`（编辑/命令/
> MCP 授权）字段，无需改动。

---

### 2. Claude Code

Claude Code 的 agent 放在 `.claude/agents/`（项目级）或
`~/.claude/agents/`（全局）。frontmatter 格式不同，需要转换。

**安装**（复制到全局，供所有项目使用）：

```bash
mkdir -p ~/.claude/agents
cp .opencode/agent/bug-hunter.md ~/.claude/agents/bug-hunter.md
```

**转换 frontmatter**：编辑 `~/.claude/agents/bug-hunter.md`，
把开头 `---` 之间的内容替换为 Claude Code 格式：

```markdown
---
name: bug-hunter
description: 永无止境地挖掘错误。白盒审计+黑盒测试+UI 视觉测试。多轮机制：每轮消耗1寿命，找到真实错误+1，欺诈-1，寿命0即死亡。
model: inherit
permission:
  - Bash
  - Edit
  - WebFetch
---
```

> 注意：`bug-hunter.md` 正文中引用的 `.opencode/agent/verify_life.py`、
> `launch_bug_hunter.py` 路径是相对仓库根的，**必须在 bug-hunter 仓库内运行**
> 或在启动前 `cd` 到该仓库。Claude Code 的 agent 继承主会话工具，Playwright
> MCP 需要在 `~/.claude.json` 或项目 `.mcp.json` 里单独配置。

**使用**：在 Claude Code 里 `@bug-hunter 开始挖掘`。

---

### 3. Codex (OpenAI)

Codex 使用 **skill** 机制（`~/.codex/skills/<name>/SKILL.md` 或项目
`.codex/skills/`）。把 bug-hunter 装成 skill，让它作为"工作模式"被加载。

**安装**：

```bash
mkdir -p ~/.codex/skills/bug-hunter
# 提取正文（去掉 opencode 专属 frontmatter），另加 skill 头
cp .opencode/agent/bug-hunter.md ~/.codex/skills/bug-hunter/SKILL.md
```

编辑 `~/.codex/skills/bug-hunter/SKILL.md`，把 `---` 之间的内容替换为：

```markdown
---
name: bug-hunter
description: >
  对抗性审计模式：白盒+黑盒+UI 视觉，多轮循环挖 bug。
  Triggers on: 找bug, 挖错误, 审计代码, UI bug, 测试找错
---
```

> Codex 没有 opencode 那样的 `permission` frontmatter 字段，权限由
> `~/.codex/config.toml` 的 `approval_policy` 控制。建议至少 `onRequest`
> 级别以便 agent 跑测试、起服务、改代码验证。

**使用**：在 Codex 会话中要求"使用 bug-hunter skill"或直接描述任务
（如"用 bug-hunter 模式审计这个仓库"），skill 会被自动加载。

---

### 4. Pi (Pi CLI / Gemini)

Pi 同样使用 skill 机制（`~/.pi/skills/<name>/SKILL.md` 或项目 `.pi/skills/`）。

**安装**：

```bash
mkdir -p ~/.pi/skills/bug-hunter
cp .opencode/agent/bug-hunter.md ~/.pi/skills/bug-hunter/SKILL.md
```

编辑 frontmatter，替换为 skill 格式（同 codex）：

```markdown
---
name: bug-hunter
description: >
  对抗性审计模式：白盒+黑盒+UI 视觉，多轮循环挖 bug。
  Triggers on: 找bug, 挖错误, 审计代码, UI bug, 测试找错
---
```

**使用**：在 Pi 会话里说"加载 bug-hunter"，或直接给出挖 bug 任务。

---

### 5. 其他工具（通用做法）

任何支持「把一份 markdown 提示词注入会话/作为 agent」的工具（Cursor、
Cursor Agent、Continue、Aider 等），通用做法：

1. 取 `bug-hunter.md` 的**正文部分**（`---` 之后的所有内容）。
2. 按工具自身的 agent/skill 格式加上 frontmatter（看上面任一例子）。
3. 让 agent 以该提示词为工作模式，在仓库内运行（保证 `.opencode/agent/`
   路径可用）。

---

## UI 挖 bug 快速上手

独立 bug-hunter 能自己发现 UI bug。前提：目标 Web 应用可访问
（本地 dev server 或线上 URL）。

```
向 bug-hunter 发起任务，例如：
「黑盒模式，UI 视觉面，目标 http://localhost:3000，挖布局和交互 bug」
```

agent 会按标准流程执行：

1. `browser_navigate` 打开目标 → `browser_snapshot` 读 DOM
2. 375/768/1024/1440 多断点 `browser_resize` + 截图对比
3. `browser_evaluate` 读 `getBoundingClientRect` 做几何断言
4. 塞长文本/CJK/emoji/超长串验证截断溢出
5. 交互轰炸：狂按 Tab 找焦点陷阱、重复点击、后退导航
6. 覆盖 loading/error/empty/disabled 状态 + 主题对比度

> OpenCode 用户无需额外配置（`opencode.json` 已内置 Playwright MCP）。
> 其他工具需自行配置对应 MCP（`npx @playwright/mcp@latest`）。

---

## 常见问题

**Q: 为什么启动时要跑 `launch_bug_hunter.py pre`？**
> 它会先 `check`（校验寿命文件一致性）再 `snapshot`（建立基线快照）。
> 运行结束后 `post` 会 `diff` 核对 life 变化是否合法，检出"自洽撒谎"并回滚。
> 这是防 agent 自评舞弊的硬防线，别跳过。

**Q: agent 说我"死亡"了怎么办？**
> 寿命归 0 = 停止挖掘（这是机制设计）。想重置重新开始：
> `python3 .opencode/agent/verify_life.py reset`
> 然后重新 `pre`。

**Q: 提示词里的 `.opencode/agent/` 路径在别的工具下还能用吗？**
> 能，前提是 agent 在当前仓库内运行（该目录随仓库一起存在）。
> 若放在全局 agent 目录且面向任意项目，需把脚本路径改为绝对路径。

**Q: UI 挖 bug 报"Playwright 不可用"？**
> 确认 `opencode.json` 存在且 npx 可用（`npx @playwright/mcp@latest`）。
> 首次运行会自动下载浏览器，需网络。

---

## 安全与合规

- agent 有完整 bash + 编辑权限，**只应在你授权的仓库/范围内运行**。
- 审计中读到的密钥/凭据禁止写入 findings/报告（agent 提示词已强制）。
- 破坏性操作限于验证 bug 所需，验证完恢复现场。
- 建议：用独立用户/容器跑 agent 获得硬隔离（见 `lockdown.sh` 注释）。
