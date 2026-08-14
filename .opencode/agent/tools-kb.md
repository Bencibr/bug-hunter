# 本地工具知识库（tools-kb）

> 机制：**本地优先，搜索兜底**。
> 每次真实搜索验证过的工具知识，沉淀到本文件。下次遇到同类型项目：
> ① 先查本库——命中则**本地优先**（除非用户明确要求重新搜索）；
> ② 未命中才真实搜索，搜完把结果回写本库（知识持续积累，不靠记忆）。
>
> 与「记忆库偷懒」的区别：本库是**本地文件证据**（有来源引用、有验证日期），
> 不是 LLM 记忆——查本库 = 查沉淀的真实知识，跳过本库直接凭记忆 = 偷懒。
>
> 维护：每搜一次新项目类型，把「测试类型 → 项目类型 → 工具 + 来源」追加
> 到对应分类下。工具过时用 `⏰` 标注待重新验证。

---

## 黑盒测试工具

### Web/API（前后端分离）
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| postmcp | API 契约轰炸（REST/GraphQL/WS/断言） | 已装 v1.1.0 | 2026-08-14 |
| playwright | UI 视觉/交互（多断点截图/几何断言） | 已装 | 2026-08-14 |
| fuzz_input.py | 变异模糊矩阵 | 自研 | 2026-08-14 |
| minimize_repro.py | 异常输入最小化 | 自研 | 2026-08-14 |

### TUI/终端交互
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| agent-tty | terminal 版 Playwright（截图/录像） | coder/agent-tty | 2026-08-14 |
| pexpect | Python PTY 交互/断言 | pexpect 4.9.0 | 2026-08-14 |
| expectrl | Rust PTY 交互 | zhiburt/expectrl | 2026-08-14 |

### Android 移动应用
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| MobSF | APK 静态安全扫描（21595★） | MobSF/Mobile-Security-Framework | 2026-08-14 |
| jadx | APK→Java 反编译 | 社区标准 | 2026-08-14 |
| apktool | 资源/Manifest 反编译 | 社区标准 | 2026-08-14 |
| objection | Frida 运行时探索（9315★） | sensepost/objection | 2026-08-14 |
| Frida | 运行时 hook（hooker 5270★） | frida 生态 | 2026-08-14 |
| Appium | 跨平台 UI 自动化 | AppiumTestDistribution | 2026-08-14 |
| SoloPi | Android 自动化测试（6202★） | alipay/SoloPi | 2026-08-14 |
| Detox | RN 端到端（12006★） | wix/Detox | 2026-08-14 |
| Kaspresso | Kotlin UI 测试（1922★） | KasperskyLab/Kaspresso | 2026-08-14 |
| adb | 设备控制万能 | Android SDK | 2026-08-14 |

---

## 白盒测试工具

### Java
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| mvn/gradle | 构建 | 已装 gradle | 2026-08-14 |
| JUnit 5 | 单测 | 随项目 | 2026-08-14 |
| JaCoCo | 覆盖率（未覆盖分支=定向挖点） | 社区标准 | 2026-08-14 |
| SpotBugs/PMD | 静态分析 | 社区标准 | 2026-08-14 |
| jstack/jmap/jstat/jcmd | JVM 诊断 | JDK 自带 | 2026-08-14 |
| CFR | 反编译（比 javap 强） | 社区标准 | 2026-08-14 |

### Rust
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| cargo | 构建/测试 | 已装 1.97 | 2026-08-14 |
| tarpaulin | 覆盖率 | 社区标准 | 2026-08-14 |
| clippy | 静态分析 | 社区标准 | 2026-08-14 |
| cargo miri | unsafe 未定义行为 | 社区标准 | 2026-08-14 |
| cargo geiger | unsafe 热点统计 | 社区标准 | 2026-08-14 |
| cargo-fuzz / honggfuzz-rs | 深度模糊 | rust-fuzz/honggfuzz-rs (501★) | 2026-08-14 |
| cargo-audit | 依赖漏洞 | RustSec | 2026-08-14 |
| egui-driver | egui GUI 自动化 | ryo33/egui-driver | 2026-08-14 |
| tauri-webdriver | Tauri macOS E2E | danielraffel/tauri-webdriver | 2026-08-14 |
| conduct | Tauri 跨平台 driver | matthunz/conduct (52★) | 2026-08-14 |

### Python / Go / JS
| 语言 | 测试 | 覆盖率 | 静态分析 |
|------|------|--------|---------|
| Python | pytest | coverage | ruff/mypy/bandit |
| Go | go test | go test -cover | go vet/staticcheck |
| JS/TS | vitest/jest | c8 | eslint/tsc |

---

## 数据库/数据工具（黑盒造数据+观测）

| 工具 | 用途 | 说明 |
|------|------|------|
| redis-cli | Redis 缓存/会话观测 | 无 MCP 时用 CLI |
| psql | PostgreSQL 查询/造数 | 无 MCP 时用 CLI |
| sqlite3 | SQLite 读写 | Android 应用常用 |
| 数据库 MCP | 统一观测接口 | 按项目配 |

---

## 待验证/备忘
- ⏰ rust GUI 工具（egui-driver 等）下次遇到 Rust 桌面项目时确认仍活跃
- ⏰ Android 工具链（MobSF/Frida 版本）遇 Android 项目时确认
