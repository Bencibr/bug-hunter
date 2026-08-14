#!/usr/bin/env python3
"""corpus_fetch.py 的单元测试 — 验证搜索/下载/提取/去重逻辑（mock 网络）。"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENT_DIR = Path(__file__).resolve().parent.parent / ".opencode" / "agent"
sys.path.insert(0, str(AGENT_DIR))

import corpus_fetch as cf  # noqa: E402


class CorpusFetchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="corpus-test-"))
        # 隔离种子目录
        cf.SEED_CORPUS = self.tmp / "seed_corpus"
        cf.SEED_CORPUS.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- search_repos ----

    @mock.patch("corpus_fetch._get")
    def test_search_repos_parses_items(self, mock_get):
        mock_get.return_value = {
            "items": [
                {"full_name": "a/b"},
                {"full_name": "c/d"},
            ]
        }
        repos = cf.search_repos("python", token=None)
        self.assertEqual(repos, ["a/b", "c/d"])
        # 验证搜索 URL 含 language 与排序
        url = mock_get.call_args[0][0]
        self.assertIn("language:python", url)
        self.assertIn("sort=stars", url)

    @mock.patch("corpus_fetch._get", return_value=b"{}")
    def test_search_repos_no_items(self, _):
        self.assertEqual(cf.search_repos("python", None), [])

    @mock.patch("corpus_fetch._get")
    def test_search_repos_with_query_includes_query(self, mock_get):
        """按项目类型定制：query 拼进 URL，分隔用 +，内部空格用 %20。"""
        mock_get.return_value = {"items": [{"full_name": "a/b"}]}
        cf.search_repos("python", token=None, query="json parser")
        url = mock_get.call_args[0][0]
        self.assertIn("language:python+json%20parser", url)
        self.assertNotIn("json parser", url)  # 原始空格不应出现（未编码）

    # ---- list_source_files ----

    @mock.patch("corpus_fetch._get")
    def test_list_source_files_filters_by_ext(self, mock_get):
        mock_get.return_value = {
            "tree": [
                {"type": "blob", "path": "main.py"},
                {"type": "blob", "path": "util.py"},
                {"type": "blob", "path": "README.md"},
                {"type": "blob", "path": "data.json"},
                {"type": "tree", "path": "dir"},
            ]
        }
        files = cf.list_source_files("repo/name", "python", None, limit=50)
        self.assertEqual(files, ["main.py", "util.py"])

    # ---- extract_seeds ----

    def test_extract_seeds_skips_comments_and_imports(self):
        code = 'import os\nfrom x import y\n# comment\ndef f():\n    return 1\n"str"\n    \n'
        seeds = cf.extract_seeds(code, "python", limit=50)
        self.assertIn("def f():", seeds)
        self.assertIn('"str"', seeds)
        self.assertNotIn("import os", seeds)
        self.assertNotIn("# comment", seeds)

    def test_extract_seeds_truncates_long_lines(self):
        long = "x = " + "a" * 600
        seeds = cf.extract_seeds(long, "python", limit=50)
        self.assertEqual(seeds, [])  # 超 500 字符被跳过

    def test_extract_seeds_respects_limit(self):
        code = "\n".join(f"v{i} = {i}" for i in range(100))
        seeds = cf.extract_seeds(code, "python", limit=5)
        self.assertEqual(len(seeds), 5)

    # ---- dedup_append ----

    def test_dedup_append_merges_without_duplicates(self):
        cf.dedup_append("python", ["a = 1", "b = 2"])
        added, total = cf.dedup_append("python", ["b = 2", "c = 3"])
        self.assertEqual(added, 1)  # b=2 重复，只新增 c=3
        self.assertEqual(total, 3)
        content = (cf.SEED_CORPUS / "python.txt").read_text(encoding="utf-8")
        self.assertEqual(content.count("b = 2"), 1)

    # ---- main 端到端（mock 网络）----

    def test_main_dry_run_no_download(self):
        with mock.patch.object(sys, "argv",
                               ["corpus_fetch", "--lang", "python", "--dry-run"]), \
             mock.patch("corpus_fetch.search_repos", return_value=["a/b"]):
            rc = cf.main()
        self.assertEqual(rc, 0)

    @mock.patch("corpus_fetch.search_repos", return_value=["repo/x"])
    @mock.patch("corpus_fetch.list_source_files", return_value=["a.py", "b.py"])
    @mock.patch("corpus_fetch.fetch_raw",
                side_effect=["def f():\n    return 1\n", 'x = "hi"\n'])
    @mock.patch.object(sys, "argv",
                       ["corpus_fetch", "--lang", "python",
                        "--count", "10", "--per-repo", "2", "--seed", "1"])
    def test_main_writes_seeds(self, *_):
        rc = cf.main()
        self.assertEqual(rc, 0)
        f = cf.SEED_CORPUS / "python.txt"
        self.assertTrue(f.is_file())
        content = f.read_text(encoding="utf-8")
        self.assertIn("def f():", content)

    @mock.patch("corpus_fetch.list_source_files", return_value=["a.py"])
    @mock.patch("corpus_fetch.fetch_raw", return_value='def parse(s):\n    return s\n')
    @mock.patch.object(sys, "argv",
                       ["corpus_fetch", "--lang", "python",
                        "--repo", "owner/json-parser",
                        "--count", "5", "--per-repo", "1", "--seed", "1"])
    def test_main_with_repo_skips_search(self, *_):
        """--repo 指定仓库：跳过 search_repos，直接用指定仓库。"""
        with mock.patch("corpus_fetch.search_repos") as mock_search:
            rc = cf.main()
        self.assertEqual(rc, 0)
        mock_search.assert_not_called()  # 指定仓库不触发搜索
        content = (cf.SEED_CORPUS / "python.txt").read_text(encoding="utf-8")
        self.assertIn("def parse(s):", content)

    @mock.patch("corpus_fetch.search_repos", return_value=["repo/x"])
    @mock.patch("corpus_fetch.list_source_files", return_value=["a.py"])
    @mock.patch("corpus_fetch.fetch_raw", return_value='def parse(s):\n    return s\n')
    @mock.patch.object(sys, "argv",
                       ["corpus_fetch", "--lang", "python",
                        "--query", "json parser",
                        "--count", "5", "--per-repo", "1", "--seed", "1"])
    def test_main_with_query_passes_to_search(self, *_):
        """--query 定制搜索：query 关键词传给 search_repos。"""
        rc = cf.main()
        self.assertEqual(rc, 0)
        # search_repos 被调用且收到 query 参数
        kwargs = cf.search_repos.call_args
        self.assertEqual(kwargs.kwargs.get("query"), "json parser")


if __name__ == "__main__":
    unittest.main(verbosity=2)
