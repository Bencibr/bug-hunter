#!/usr/bin/env bash
# lockdown.sh — 加固 bug-hunter 外部防线文件（同权限逃逸的 OS 层缓解）
#
# 背景：bug-hunter 拥有完整 bash + 文件读权限，理论上可复制/篡改校验器
# 脚本（cp verify_life.py /tmp/x.py 修改后运行）或改写快照基线，从而绕过
# 外部防线。opencode 的 permission 挡「诚实越界」，但挡不住「恶意 + 全权限」。
#
# 本脚本把校验器/启动器/快照设为「只读」，作为文件系统层防线：
#   - verify_life.py / launch_bug_hunter.py → chmod 444（只读）
#   - bug-hunter-life.json.snapshot（基线）→ chmod 444（只读，防改写基线）
#   - bug-hunter-life.json（agent 结算）→ 保持可写
#
# 注意：单用户环境（owner=运行者）下 chmod 可被同用户 chmod 回去，本脚本是
# 威慑+防误操作层；真正的硬隔离需要把 agent 跑在不同用户/容器/沙箱里，
# 此时本脚本 + 文件属主不同即构成真实防线。
set -euo pipefail
cd "$(dirname "$0")"

for f in verify_life.py launch_bug_hunter.py; do
    if [[ -f "$f" ]]; then
        chmod a-w "$f"
        echo "  ✓ $f → 只读"
    fi
done
if [[ -f bug-hunter-life.json.snapshot ]]; then
    chmod a-w bug-hunter-life.json.snapshot
    echo "  ✓ bug-hunter-life.json.snapshot → 只读（基线锁定）"
fi
echo
echo "外部防线文件已锁定为只读；bug-hunter-life.json 保持可写（agent 结算用）。"
echo "解锁（后续维护）：chmod u+w verify_life.py launch_bug_hunter.py"
