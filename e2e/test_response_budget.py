import importlib.util
import json
import pathlib
import subprocess
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "WebSearchAgent.py"
spec = importlib.util.spec_from_file_location("web_search_agent", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResponseBudgetTests(unittest.TestCase):
    def agent(self, budget=10_000):
        agent = module.WebDeepSearch({"response_budget_bytes": budget})
        agent.error_counts.clear()
        agent.skipped_url_reasons.clear()
        return agent

    def assert_bounded(self, agent, response):
        encoded = agent._serialize_response(response).encode("utf-8")
        self.assertLessEqual(len(encoded), agent.config["response_budget_bytes"])
        self.assertEqual(json.loads(encoded), response)

    def test_small_response_keeps_legacy_shape_and_full_content(self):
        agent = self.agent()
        agent.sources = [{"url": "https://example.com/a", "title": "A", "snippet": "short", "content": "body"}]
        result = agent._build_raw_response("q")
        self.assertEqual(result["sources"][0]["content"], "body")
        self.assertNotIn("mode", result)
        self.assert_bounded(agent, result)

    def test_large_sources_compact_and_retain_prioritized_content(self):
        agent = self.agent(7_500)
        agent.sources = [
            {"url": f"https://example{i}.com/page", "title": f"Title {i}", "snippet": "s" * (30 - i), "content": "é" * 8000}
            for i in range(10)
        ]
        result = agent._build_raw_response("query")
        self.assertEqual(result["mode"], "compact")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["source_count"], len(result["sources"]))
        self.assertLessEqual(result["source_count"], 10)
        self.assertTrue(all(s["url"] and s["title"] and s["snippet"] is not None and s["domain"] for s in result["sources"]))
        self.assertTrue(all(s["content_length"] == 8000 for s in result["sources"]))
        self.assertEqual(result["retained_content_count"] + result["omitted_content_count"], sum(bool(s["content"]) for s in agent.sources))
        self.assertGreater(result["retained_content_count"], 0)
        self.assert_bounded(agent, result)

    def test_empty_content_is_valid_and_boundary_budget(self):
        agent = self.agent()
        agent.sources = [{"url": "https://example.com", "title": "", "snippet": "", "content": ""}]
        full = agent._build_raw_response("q")
        exact = len(agent._serialize_response(full).encode("utf-8"))
        agent.config["response_budget_bytes"] = exact
        self.assert_bounded(agent, agent._build_raw_response("q"))

    def test_deep_search_many_sources_never_exceeds_budget(self):
        agent = self.agent(10_000)
        agent.iterations_used = 5
        agent.sources = [
            {"url": f"https://site{i}.example/path", "title": str(i), "snippet": "snippet", "content": "x" * 8000}
            for i in range(10)
        ]
        result = agent._build_raw_response("deep query")
        self.assertEqual(result["iterations_used"], 5)
        self.assert_bounded(agent, result)


class PublicCliArgumentTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            ["python3", str(SCRIPT), "--query", "unit test", "--max-sources", "1", "--deep-search", "false", *arguments],
            capture_output=True, text=True, timeout=10,
        )

    def test_public_options_are_listed(self):
        result = subprocess.run(["python3", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=5)
        for option in ("--max-iterations", "--max-content-length", "--timeout", "--max-total-time"):
            self.assertIn(option, result.stdout)

    def test_out_of_range_arguments_fail_before_network_access(self):
        for args in (("--max-iterations", "11"), ("--max-content-length", "499"), ("--timeout", "61"), ("--max-total-time", "9")):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be between", result.stderr)

    def test_valid_arguments_pass_validation(self):
        # Search dependency may not be installed in every test environment; in
        # that case execution should fail normally, not with an argument error.
        result = self.run_cli("--max-iterations", "1", "--max-content-length", "500", "--timeout", "5", "--max-total-time", "10")
        self.assertNotEqual(result.returncode, 2)
        self.assertNotIn("must be between", result.stderr)
        # Verify the output is valid JSON with expected keys
        if result.stdout.strip():
            data = json.loads(result.stdout)
            self.assertIn("query", data)
            self.assertIn("sources", data)


if __name__ == "__main__":
    unittest.main()
