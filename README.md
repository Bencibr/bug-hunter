# Bug-Hunter Agent

> **Version 0.0.7** · [Git tag: v0.0.7](https://github.com/Bencibr/bug-hunter)

永无止境地挖掘错误的对抗性审计 Agent。白盒源码审计 + 黑盒成品测试
（CLI / PTY / 数据接口 / **UI 视觉交互面** / **API 服务接口面**），多轮循环
机制：每轮消耗 1 点寿命做一轮全量发现，找到真实错误 +1，欺诈 -1，
寿命归 0 即死亡。

---

## 机制一览

- **多轮循环**：`life > 0` 就自动进入下一轮，直到寿命耗尽死亡。
- **寿命记账**：`verify_life.py` 是外部权威校验器，防止 agent 自评舞弊
  （篡改寿命、伪造证据、绕过结算都会被 diff 拦截并回滚）。
- **错题集**：`mistake-book.md` 沉淀历轮 bug 的「分类 + 根因 + 同类排查点」，
  每轮勘察优先通读，把历史教训变成主动排查清单。
- **应并发，尽并发**：宪法级执行原则——并行勘察/挖掘/验证/修复是默认方式，
  多方向、多接口面、多输入矩阵同时推进，除独占资源/顺序依赖外一律并行。
- **全覆盖宪法（最高优先）**：审计范围一经确定，**所有模块必须 100% 被挖掘
  覆盖**——任何模块不得因"难/耗时"跳过；死亡/收工报告须 `已覆盖 100%`，
  未覆盖/挂起须清零或给出可豁免原因。效率优化服务于覆盖，不替代覆盖。
- **先易后难（效率策略）**：在保证全覆盖前提下按「难度升序 + 命中降序」调度
  ——易模块快速过攒覆盖底盘，难模块留足预算攻坚；卡住标「挂起」稍后补，
  不豁免。
- **化整为零（分治 + 覆盖追踪）**：把项目拆成模块清单
  `module-coverage.md`（每模块打难度/命中分），并行任务分头轰炸各模块，
  用清单追踪覆盖状态（未覆盖→挖掘中→挂起→已覆盖），确保不留死角。
- **测试分层（效率）+ 深度递进 + 覆盖引导（挖掘）**：冒烟（秒级快筛）→ 聚焦
   （受影响模块）→ 全量（回归）分层跑，先快后深；静态读码→动态跑测→插桩→
   反汇编逐层递进，根因链完整才算挖透；用 `coverage` 定位未覆盖路径定向挖；
   异常样本用 `minimize_repro.py` 最小化，解析器类用 `fuzz_input.py` 变异矩阵
   并发轰（种子不足时 `corpus_fetch.py --lang <语言> --query "<项目类型>"` 并发
   搜**同类**开源项目扩充，或 `--repo` 指定对照实现提取——种子贴合被测材质）。
 - **工欲善其事，必先利其器（工具即杠杆）**：开工先自我排查工具清单——自研
   fuzz/minimize/corpus + postmcp（API 接口面）+ playwright（UI 面）+ 系统
   timeout/objdump/curl/coverage，按场景选工具、缺的先装/先造再打，不硬凿。
 - **兵马未动，粮草先行（开工第一宪法）**：工具没准备好，绝不开工。开工前
  四步：① 知彼（了解项目是什么/什么功能/什么栈）② 调研（**本地优先 + 30 天
  有效期 → 搜索兜底**：先查 `tools-kb.md` 工具知识库，命中且 ≤30 天则复用
  （除非用户要求重搜），命中但 >30 天必须重搜更新，未命中才真实搜索并回写
  本库——禁止记忆库偷懒与过期知识复用）③ 定策（**先定
  测试类型黑盒/白盒/自动化，再按项目类型选工具**：黑盒→postmcp/playwright/
  agent-tty/数据库 MCP/模糊，白盒→语言专项 JUnit/JaCoCo/SpotBugs 等，
  自动化→项目测试命令+自研工具；**只装当前项目需要的**，复杂项目多工具按
  模块分配协作）④ 备粮（只装需要
  且缺的工具）。工具没就绪不开始挖掘。
- **三思而行 · 从不打无准备的仗 · 知己知彼百战不殆（哲学）**：动手前先想
  清楚打什么/怎么打/打到什么程度；备足弹药再开战（了解目标+备好工具+攒好
  语料）；知己知彼——先侦察后火力，对目标一无所知就开工 = 蒙眼开枪。
- **三思而行 · 从不打无准备的仗 · 知己知彼百战不殆（哲学）**：动手前先想
  清楚打什么/怎么打/打到什么程度；备足弹药再开战（了解目标+备好工具+攒好
  语料）；知己知彼——先侦察后火力，对目标一无所知就开工 = 蒙眼开枪。
- **因地制宜 · 因材施教**：按目标形态选策略（白盒/黑盒/UI/PTY/API）、按代码材质
  选手法（解析器→模糊、状态机→序列、并发→竞态、安全→越权、UI→截图断言），
  按环境/寿命调投入——不套模板，打七寸。
- **启动必询修复模式**：全新会话启动先询问用户「是否自动修复 bug」——自动修复走
  TDD+Live 全链路；只记录把 bug 写进 `bug-log.md`（不改码）。**恢复会话且未死亡
  不询问**，沿用上次模式继续。两种模式都做完整挖掘，且都适用并行。
- **Reset 需 ask 授权**：`verify_life.py reset` 为 `ask` 权限——死亡后 agent
  发起重置调用时弹出用户确认，确认即放行，非交互场景不生效。
- **重复不计命，并行按量计命**：与 `history` 或 `bug-log.md` 重复的发现不计命；
  一轮并行发现多个非重复 bug 每项 +1（受 MAX_PER_ROUND 上限），两种模式通用。
- **修复纪律（TDD + Live + 留痕）**：每个可修 bug 走 TDD 红黑闭环（先写失败用例→
  修复→转绿→回归），并强制 **Live 真实环境复验**——用原始复现命令重跑 /
  UI 同视口截图做几何断言，单测转绿不算修好，Live 复验通过才算 `fixed`；
  每次修复写日志，每轮结束 git commit（`fix(roundN): 摘要`），死亡前构建
  `test-report.md` 汇总测试报告。
- **UI 挖 bug**：通过 Playwright 打开网页，多断点截图 + DOM 几何断言 +
  交互轰炸 + 状态覆盖，找布局崩塌、焦点陷阱、文案截断、对比度不足等视觉 bug。
 - **API 挖 bug**：通过 **postmcp** 对 HTTP(REST)/GraphQL/WebSocket 接口做
   契约轰炸——参数边界/越权/注入/状态码断言，配合 Swagger/Postman 导入全接口
   清单。可与 Playwright 配合（同应用 API 层 + UI 层互证），也可单独使用。
- **TUI 挖 bug**：通过 **agent-tty**（terminal 版 Playwright）/ **pexpect** 驱动
  TUI/REPL/向导——按键序列轰炸、状态机违例、退出路径，截图/录像可复核。
  有成熟工具优先用，不自研轮子。
- **测试广度保障**：71 例单元测试覆盖校验器/启动协议/环境自检（含 TUI 工具）/
  最小化/模糊/种子扩充（含按项目类型定制搜索），外加一致性测试防文档漂移
  （版本/引用/权限/覆盖）——改动不怕破坏。

### 文件结构

| 文件 | 作用 |
|------|------|
| `.opencode/agent/bug-hunter.md` | Agent 定义（核心提示词 + 生命周期规则 + 宪法） |
| `.opencode/agent/verify_life.py` | 寿命校验器（check/repair/settle/reset/snapshot/diff/restore/selfhash，含自哈希防篡改） |
| `.opencode/agent/launch_bug_hunter.py` | 启动协议（pre 输出外部基线 / post 核对 / status） |
| `.opencode/agent/lockdown.sh` | OS 层加固（把校验器/基线设为只读） |
| `.opencode/agent/setup_ui_env.py` | UI/TUI 环境自检/自动补装（node/playwright/浏览器/agent-tty/pexpect） |
| `.opencode/agent/mistake-book.md` | 错题集（反思归类复用） |
| `.opencode/agent/bug-log.md` | bug 记录清单（只记录模式的产物 + 全模式去重依据） |
| `.opencode/agent/module-coverage.md` | 模块覆盖清单（化整为零：拆分模块 + 覆盖追踪） |
| `.opencode/agent/tools-kb.md` | 工具知识库（本地优先：搜索验证过的工具沉淀，同类型项目直接复用） |
| `.opencode/agent/minimize_repro.py` | 失败输入最小化工具（ddmin，根因集中 + 举证加速） |
| `.opencode/agent/fuzz_input.py` | 变异模糊矩阵工具（并发批量轰输入，筛异常样本） |
| `.opencode/agent/corpus_fetch.py` | 种子扩充工具（并发搜 GitHub，支持 `--query` 按项目类型/`--repo` 指定仓库） |
| `.opencode/agent/seed_corpus/` | 多语言种子语料库（10 语言，可 fuzz 扩充） |
| `.opencode/agent/bug-hunter-life.json` | 寿命状态（运行时生成，不入库） |
| `.opencode/agent/repair-audit.log` | 修复审计日志（每次 repair 留痕，不入库） |
| `.opencode/agent/findings_round*.txt` | 每轮发现记录 |
| `test-report.md` | 死亡退出前的汇总测试报告（运行时生成） |
| `tests/test_verify_life.py` | 校验器单元测试（23 例：check/settle/diff/repair/evidence/selfhash） |
| `tests/test_launch_bug_hunter.py` | 启动协议测试（5 例：pre/post/status） |
| `tests/test_setup_ui_env.py` | 环境自检测试（12 例：node/npx/浏览器/TUI 工具检测） |
| `tests/test_minimize_repro.py` | 最小化工具测试（3 例） |
| `tests/test_fuzz_input.py` | 模糊工具测试（9 例：变异策略/崩溃筛选/端到端） |
| `tests/test_corpus_fetch.py` | 种子扩充测试（12 例：搜索/query 定制/repo 指定/提取/去重/端到端） |
| `tests/test_consistency.py` | 一致性测试（6 例：版本/引用/权限/覆盖防漂移） |
| `tests/run_tests.sh` | 一键测试入口 |
| `opencode.json` | MCP 配置（Playwright UI + postmcp API） |

> 提示：`bug-hunter-life.json`、`.snapshot`、`repair-audit.log` 已被 `.gitignore`
> 排除。每个使用者 clone 后从初始态（life=1）各自开始，历史发现不共享。

---

## 前置要求

- **Python 3**：运行 `verify_life.py` / `launch_bug_hunter.py`
- **Node.js + npx**：运行 Playwright MCP（UI 挖 bug 才需要）
- **postmcp**（API 挖 bug 需要，未装会自动安装）：`npm install -g @bencibro/postmcp`
- **agent-tty + pexpect**（TUI 挖 bug 需要）：`npm install -g agent-tty && pip install pexpect`
  （terminal 版 Playwright，驱动 nvim/htop 等交互应用并截图/录像）
- **数据库工具**（黑盒造数据/观测/验证持久化，按项目配）：`redis-cli`/`psql`/
  `mysql` 或对应数据库 MCP
- **语言专项白盒工具**（白盒测试按项目语言配）：Java → Maven/JUnit/JaCoCo/
  SpotBugs（`./mvnw` 或 `gradle`）+ JDK 自带 `jstack`/`jmap`/`jstat`；Rust →
  cargo/tarpaulin/cargo-fuzz/miri/geiger；**Rust 桌面 GUI** → egui-driver（egui）/
  tauri-webdriver（Tauri macOS）/ conduct（Tauri 跨平台）；其他语言见
  「语言专项工具」表
- **AI 编程工具**：任选一款支持 agent/skill 的（见下文）

---

## 开发与测试

核心机制（寿命记账/防舞弊）有单元测试保障，改动后跑一键测试：

```bash
./tests/run_tests.sh
# 或
python3 -m unittest discover -s tests -p "test_*.py"
```

**测试覆盖（71 例）**：
- `test_verify_life.py`（23）— check / settle 结算护栏（credited、证据校验、
  轮号、历史去重）/ snapshot/diff/restore / repair 幽灵轮费回滚 / 篡改自校验
- `test_launch_bug_hunter.py`（5）— pre 基线+外部基线输出 / post diff 异常回滚
  / status
- `test_setup_ui_env.py`（12）— node/npx/浏览器检测、TUI 工具检测、check 汇总、缺失上报
- `test_minimize_repro.py`（3）— ddmin 最小化（去噪保触发、多 token 保留）
- `test_fuzz_input.py`（9）— 变异策略（truncate/flip/garbage/numeric/string/
  duplicate）、崩溃/超时筛选、端到端 summary+异常落盘
- `test_corpus_fetch.py`（12）— 仓库搜索解析、**--query 定制搜索（URL 编码）**、
  **--repo 指定仓库（跳过搜索）**、文件过滤、种子提取/去重、dry-run 与端到端
- `test_consistency.py`（6）— **防文档漂移**：版本一致、提示词引用文件存在、
  reset 权限为 ask、核心脚本都有测试、README 文件表一致

测试在独立临时目录运行，**不污染真实 `bug-hunter-life.json`**。

> 提示词结构：`bug-hunter.md` 保留全部行为规则（宪法/哲学/机制/反模式）；
> 错题集、bug-log、模块覆盖清单的格式模板在各自独立文件，`bug-hunter.md`
> 只引用不重复，减少上下文负担。

---

## 各工具安装与使用

### 1. OpenCode（原生支持，推荐）

本项目已内置 `.opencode/agent/bug-hunter.md` 和 `opencode.json`，clone 后即用。

```bash
git clone https://github.com/Bencibr/bug-hunter.git
cd bug-hunter
```

**启动协议**（校验基线 → 快照 → 输出外部基线 → 启动 → 结束后核对）：

```bash
python3 .opencode/agent/launch_bug_hunter.py pre
```

`pre` 会输出一行 **外部基线**（`export BH_PRE_BASELINE='...'`），请**复制保存**
（它放在 agent 会话之外，防 agent 篡改快照后绕过 diff）。然后在 opencode 中
通过 **Task 工具**调用 subagent，或输入框 `@` 提及：

```
@bug-hunter 开始挖掘
```

**全新会话启动**时 agent 会先询问：**「是否自动修复 bug？」**
- 回答「自动修复」→ agent 走 TDD + Live 完整修复链路
- 回答「只记录」→ agent 不修改代码，把发现写进 `.opencode/agent/bug-log.md`
  待后续处理；后续轮次跳过清单内已列 bug（重复不计命）；并行发现多个
  非重复 bug 按数量计命（两种模式通用）

**恢复会话（resume/续跑）且未死亡**时：agent **不询问**，直接沿用上次模式继续。

运行结束后，先恢复外部基线再核对：

```bash
# 粘贴 pre 输出的 export 行（若换了终端必须重新设置）
export BH_PRE_BASELINE='{"life": 1, ...}'
python3 .opencode/agent/launch_bug_hunter.py post
```

> OpenCode 原生支持本仓库 frontmatter 的 `mode: all`、`permission`（编辑/命令/
> MCP 授权）字段，无需改动。

**安全机制**（v0.0.2 审计修复，v0.0.7 增补）：
- 校验器内嵌自哈希校验，被 bash 篡改后拒绝执行
- settle 要求每条计命 findings 含真实文件引用或测试名（堵凭空编造刷命）
- `post` 用外部基线 diff，agent 同时改 life+snapshot 也会被检出
- repair 每次操作写入 `repair-audit.log` 审计日志，可追溯
- `verify_life.py reset` 为 `ask` 权限——重置必须经 permission 弹窗用户确认
  （交互授权），agent 无法绕过 ask 静默重置

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

## API 挖 bug 快速上手

bug-hunter 用 **postmcp** 挖 API/接口 bug。前提：目标接口可访问（本地服务
或线上），且已装 postmcp（`npm install -g @bencibro/postmcp`）。

```
向 bug-hunter 发起任务，例如：
「黑盒模式，API 服务面，目标 http://localhost:8080/api，挖接口契约和安全 bug」
```

agent 会按标准流程执行：

1. `project_create` + `env_configure`（baseUrl）+ `env_switch`
2. `env_set_allowlist` 配置目标域名白名单（安全底线，空白名单拒绝出站）
3. `swagger_import` / `postman_import` 导入接口清单（接口 = 覆盖单元）
4. `http_request` 逐接口扫 + 参数边界轰炸（超长/空/负/NaN/类型错位）
5. 越权/未鉴权探测、SQLi/命令注入、敏感字段泄漏检查
6. 状态码 + 响应结构断言（`assertions`/`jsonpathFilter`）
7. `graphql_request`（GraphQL 服务）、`ws_connect`+`ws_wait`（WebSocket）

**配合 Playwright**：同一应用的 API 层（postmcp）与前端交互层（Playwright）
可同时挖、互相印证——UI 操作背后的接口契约错误，两者交叉定位更准。
也可单独使用 postmcp 只挖接口。

> OpenCode 用户无需额外配置（`opencode.json` 已内置 postmcp MCP）。
> 其他工具需自行配置：`command: ["postmcp"]`。

---

## 常见问题

**Q: 工具选择是每次重新搜索吗？**
> 不是。走「本地优先 + 30 天有效期 → 搜索兜底」：先查 `.opencode/agent/
> tools-kb.md` 工具知识库——同类型项目命中**且验证日期 ≤ 30 天内**则直接复用
> （除非你明确要求重新搜索）；**命中但超过 30 天 = 过期**，必须重新搜索验证
> 并更新本库（工具/生态会演进）；未命中才真实搜索，搜完把工具+来源+今天
> 日期回写本库。知识持续积累且可更新，既不用每次重搜，也不靠 agent 记忆
> （本库是带来源和有效期的本地证据，不是记忆）。

**Q: postmcp 没装会怎样？**
> agent 会自动检测：工具集缺 `postmcp_*` 时运行
> `npm install -g @bencibro/postmcp` 主动安装，装完提示重启 opencode 会话
> （MCP 启动时加载）。`opencode.json` 已内置 postmcp 配置，clone 后即用。

**Q: 为什么启动时要跑 `launch_bug_hunter.py pre`？**
> 它会先 `check`（校验寿命文件一致性）再 `snapshot`（建立基线快照）。
> 运行结束后 `post` 会 `diff` 核对 life 变化是否合法，检出"自洽撒谎"并回滚。
> 这是防 agent 自评舞弊的硬防线，别跳过。

**Q: agent 说我"死亡"了怎么办？**
> 寿命归 0 = 停止挖掘（这是机制设计）。agent 死亡前会先保存 `test-report.md`
> 并提交，然后发起 `verify_life.py reset`——由于它是 `ask` 权限，会弹窗征求
> 你确认（交互场景）。确认后计数重置：
> `python3 .opencode/agent/verify_life.py reset`
> 重置后从初始态（life=1）重新开始，再跑 `pre` 启动下一个会话。

**Q: 提示词里的 `.opencode/agent/` 路径在别的工具下还能用吗？**
> 能，前提是 agent 在当前仓库内运行（该目录随仓库一起存在）。
> 若放在全局 agent 目录且面向任意项目，需把脚本路径改为绝对路径。

**Q: UI 挖 bug 报"Playwright 不可用"？**
> 先跑 `python3 .opencode/agent/setup_ui_env.py check` 看缺什么，再跑
> `install` 自动补装（node/playwright/浏览器）。补装后**重启 opencode 会话**
> 让 MCP 工具生效（MCP 在启动时加载，运行中不能热注册）。

**Q: 缺少 MCP 能自动安装吗？**
> 分两层：底层**运行时依赖**（node、@playwright/mcp、Chromium）可自动检测并
> 补装（`setup_ui_env.py install`）；但 **MCP 工具本身**由 opencode 启动时加载，
> agent 无法在会话中给自己热注册新 MCP server——补装完依赖后需重启会话生效。

**Q: 每轮修复会自动提交代码吗？**
> 会。宪法要求每轮结算后 `git commit -m "fix(roundN): <摘要>"` 提交本轮全部改动
> （源码 + 测试 + findings + 错题集 + bug-log）。未提交 = 本轮闭环未完成，
> 禁止进入下一轮。

**Q: 如何确保所有模块都被挖掘覆盖？**
> 全覆盖宪法：所有模块必须 100% 覆盖。执行上是「化整为零 + 先易后难调度」——
> agent 把项目拆成模块清单 `module-coverage.md`（每模块打难度/命中分），按
> 难度升序先易后难、命中降序并行轰炸；卡住标「挂起」稍后补上（不豁免）。
> 死亡/收工前逐一核对——**覆盖率必须 100%（Y/Y）**，未覆盖/挂起须清零或
> 给出可豁免原因，test-report.md 报告覆盖清单，确保不留死角。

**Q: 改动核心机制后如何验证没破坏？**
> 跑 `./tests/run_tests.sh`——覆盖校验器全部命令与防舞弊护栏（23 个断言用例）。
> 测试在临时目录运行，不污染真实寿命文件；同时 `verify_life.py check` 自检
> 真实状态一致性。

**Q: 「自动修复」和「只记录」两种模式有何区别？**
> 全新会话启动时会询问；恢复会话（未死亡）则不询问、沿用上次模式。自动修复：
> 发现即走 TDD+Live 修到转绿；只记录：不修改代码，把发现写入 `bug-log.md`
> 待后续处理。两种模式都做完整挖掘、都适用并行、都按「非重复 bug 数量」计命
> （与 history / bug-log 重复的不计命）。

**Q: agent 死亡时会留下什么？**
> 宪法要求死亡退出前先构建并保存 `test-report.md`（存活轮数、发现清单、修复状态、
> Live 复验结果、遗留风险、下次重启建议），随代码一起提交，再输出死亡行。
> 随后发起 `verify_life.py reset`（ask 权限，弹窗确认即重置计数数据，
> 为下一个会话做准备）。

---

## 安全与合规

- agent 有完整 bash + 编辑权限，**只应在你授权的仓库/范围内运行**。
- 审计中读到的密钥/凭据禁止写入 findings/报告（agent 提示词已强制）。
- 破坏性操作限于验证 bug 所需，验证完恢复现场。
- 建议：用独立用户/容器跑 agent 获得硬隔离（见 `lockdown.sh` 注释）。
