# 本地工具知识库（tools-kb）

> 机制：**本地优先，搜索兜底，30 天有效期**。
> 每次真实搜索验证过的工具知识，沉淀到本文件。下次遇到同类型项目：
> ① 先查本库——**命中且验证日期 ≤ 30 天内 → 本地优先**（除非用户明确要求
>    重新搜索）；
> ② **命中但超过 30 天 = 过期** → 必须重新搜索验证，用新结果更新本库条目
>    （更新验证日期）；
> ③ 未命中 → 真实搜索，搜完把结果回写本库（知识持续积累，不靠记忆）。
>
> **有效期规则（硬性）**：本库条目以「验证日期」为准，**30 天（含）内有效**。
> 超过 30 天视为过期，不得直接复用——工具/项目生态会演进，过期知识可能
> 已过时（star 变化/项目废弃/出现更优替代），必须重新搜索。除非用户明确
> 要求"直接用本地不用搜"，否则过期条目一律重新验证。
>
> 与「记忆库偷懒」的区别：本库是**本地文件证据**（有来源引用、有验证日期、
> 有有效期），不是 LLM 记忆——查本库 = 查沉淀的真实知识，跳过本库直接凭
> 记忆 = 偷懒；复用过期条目 = 用过期知识 = 偷懒。
>
> 维护：每搜一次新项目类型，把「测试类型 → 项目类型 → 工具 + 来源 + 验证
> 日期」追加到对应分类下。**过期条目用 `⏰` 标记并更新日期**（重新验证后）。
> 验证日期格式 `YYYY-MM-DD`，以当天日期为准计算是否过期（30 天窗口）。

---

## 黑盒测试工具

### Web/API（前后端分离）
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| postmcp | API 契约轰炸（REST/GraphQL/WS/断言） | npm @bencibro/postmcp 1.0.3（CLI banner 1.1.0） | 2026-08-14 |
| playwright | UI 视觉/交互（多断点截图/几何断言） | npm @playwright/mcp 0.0.79 | 2026-08-14 |
| fuzz_input.py | 变异模糊矩阵 | 自研 | 2026-08-14 |
| minimize_repro.py | 异常输入最小化 | 自研 | 2026-08-14 |

### TUI/终端交互
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| agent-tty | terminal 版 Playwright（截图/录像） | npm agent-tty 0.5.0（Node >=24,<27） | 2026-08-14 |
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

### iOS 移动应用
| 工具 | 用途 | 来源 | 验证日期 |
|------|------|------|---------|
| OWASP MASTG | 移动应用安全测试指南（13111★） | OWASP/mastg | 2026-08-14 |
| appium-xcuitest-driver | iOS UI 自动化（XCUITest 驱动，876★） | appium/appium-xcuitest-driver | 2026-08-14 |
| AutoMate | XCTest 扩展助手（290★） | PGSSoft/AutoMate | 2026-08-14 |
| frida-ios-dump | 越狱设备脱壳拉取 decrypted ipa（3906★） | AloneMonkey/frida-ios-dump | 2026-08-14 |
| objection | Frida 运行时探索（跨平台，9315★） | sensepost/objection | 2026-08-14 |
| Keychain-Dumper | Keychain 项检查（1420★） | ptoomey3/Keychain-Dumper | 2026-08-14 |
| truegaze | iOS/Android 静态分析（敏感信息，134★） | nightwatchcybersecurity/truegaze | 2026-08-14 |
| iOS_Reverse_Engineering | IPA 逆向参考（558★） | LaurieWired/iOS_Reverse_Engineering | 2026-08-14 |
| ivan-sincek/ios-penetration-testing-cheat-sheet | iOS 渗透测试速查（421★） | ivan-sincek/ios-penetration-testing-cheat-sheet | 2026-08-14 |

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
| 语言 | 测试 | 覆盖率 | 静态分析 | 验证日期 |
|------|------|--------|---------|---------|
| Python | pytest | coverage | ruff/mypy/bandit | 2026-08-14 |
| Go | go test | go test -cover | go vet/staticcheck | 2026-08-14 |
| JS/TS | vitest/jest | c8 | eslint/tsc | 2026-08-14 |

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
- ✅ 自研 corpus_fetch.py 已支持按项目定制：`--query "json parser"`（按项目类型
  搜，种子贴合被测材质）+ `--repo serde-rs/json`（指定仓库提取）——遇解析器/
  格式类目标时用项目类型 query 拉同类项目种子，命中率高于纯语言种子
- 本库所有条目验证日期均为 2026-08-14，**2026-09-13 后全部过期**需重新验证
