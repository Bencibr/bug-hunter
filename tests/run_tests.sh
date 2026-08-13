#!/usr/bin/env bash
# run_tests.sh — bug-hunter 全量测试入口
# 覆盖：verify_life 防舞弊、launch 启动协议、setup_ui_env 环境自检、
#       minimize_repro 最小化、项目一致性（版本/引用/权限/测试覆盖）
set -euo pipefail
cd "$(dirname "$0")/.."   # 回到仓库根

echo "=== 单元测试（全部）==="
python3 -m unittest discover -s tests -p "test_*.py" -v 2>&1 | tail -3
echo
echo "=== 校验器自检（真实状态一致性）==="
python3 .opencode/agent/verify_life.py check
echo
echo "✓ 全部通过"
