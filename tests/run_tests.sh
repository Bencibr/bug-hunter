#!/usr/bin/env bash
# run_tests.sh — bug-hunter 核心机制一键测试
# 覆盖 verify_life.py 的防舞弊逻辑（check/settle/diff/repair/evidence/selfhash）
set -euo pipefail
cd "$(dirname "$0")/.."   # 回到仓库根

echo "=== verify_life.py 单元测试 ==="
python3 tests/test_verify_life.py
echo
echo "=== 校验器自检（真实状态一致性）==="
python3 .opencode/agent/verify_life.py check
echo
echo "✓ 全部通过"
