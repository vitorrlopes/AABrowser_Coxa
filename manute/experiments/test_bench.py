"""Testes do harness. Rodar com: python3 -m unittest -v (dentro de experiments/)."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import bench


def _sse(events: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


class _FakeLlamaServer(BaseHTTPRequestHandler):
    events: list[dict] = []
    last_body: dict = {}

    def do_POST(self) -> None:  # noqa: N802 (nome exigido pela stdlib)
        length = int(self.headers["Content-Length"])
        type(self).last_body = json.loads(self.rfile.read(length))
        payload = _sse(type(self).events)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        pass


def _chunk(text: str) -> dict:
    return {"choices": [{"delta": {"content": text}}]}


class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeLlamaServer)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_uses_server_timings_when_available(self) -> None:
        _FakeLlamaServer.events = [
            _chunk("Olá"), _chunk(", mundo"),
            {"choices": [], "timings": {"predicted_n": 7, "predicted_per_second": 12.5,
                                        "prompt_per_second": 80.0}},
        ]
        result = bench.OpenAICompatibleEngine(self.base_url).generate("oi", max_tokens=16)

        self.assertEqual(result.text, "Olá, mundo")
        self.assertEqual(result.completion_tokens, 7)
        self.assertEqual(result.tokens_source, "server")
        self.assertEqual(result.decode_tps, 12.5)
        self.assertEqual(result.prompt_tps, 80.0)
        self.assertIsNotNone(result.ttft_s)
        self.assertEqual(_FakeLlamaServer.last_body["max_tokens"], 16)
        self.assertTrue(_FakeLlamaServer.last_body["stream"])

    def test_falls_back_to_chunk_count(self) -> None:
        _FakeLlamaServer.events = [_chunk("a"), _chunk("b"), _chunk("c")]
        result = bench.OpenAICompatibleEngine(self.base_url).generate("x", max_tokens=8)

        self.assertEqual(result.completion_tokens, 3)
        self.assertEqual(result.tokens_source, "chunks")

    def test_empty_generation_has_no_ttft(self) -> None:
        _FakeLlamaServer.events = []
        result = bench.OpenAICompatibleEngine(self.base_url).generate("x", max_tokens=8)

        self.assertIsNone(result.ttft_s)
        self.assertIsNone(result.decode_tps)
        self.assertEqual(result.completion_tokens, 0)


class PolicyTest(unittest.TestCase):
    def test_remote_endpoint_blocked_by_default(self) -> None:
        with self.assertRaises(PermissionError):
            bench.OpenAICompatibleEngine("https://api.example.com")

    def test_remote_endpoint_allowed_explicitly(self) -> None:
        engine = bench.OpenAICompatibleEngine("https://api.example.com", allow_remote=True)
        self.assertEqual(engine.base_url, "https://api.example.com")

    def test_invalid_url_rejected(self) -> None:
        with self.assertRaises(ValueError):
            bench.ensure_allowed("not a url", allow_remote=False)


class SummaryTest(unittest.TestCase):
    def test_median_ignores_missing_values(self) -> None:
        records = [
            {"prompt_id": "p1", "ttft_s": 1.0, "decode_tps": 10.0, "total_s": 5.0},
            {"prompt_id": "p1", "ttft_s": 3.0, "decode_tps": None, "total_s": 7.0},
            {"prompt_id": "p1", "ttft_s": 2.0, "decode_tps": 14.0, "total_s": 6.0},
        ]
        summary = bench.summarize(records)["p1"]

        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["ttft_s_median"], 2.0)
        self.assertEqual(summary["decode_tps_median"], 12.0)
        self.assertEqual(summary["total_s_median"], 6.0)


class FakeEngine:
    name = "fake"

    def generate(self, prompt: str, *, max_tokens: int) -> bench.Generation:
        return bench.Generation(text=prompt[:max_tokens], ttft_s=0.1, total_s=1.0,
                                completion_tokens=max_tokens, tokens_source="server",
                                decode_tps=10.0)


class RunBenchmarkTest(unittest.TestCase):
    def test_engine_is_swappable_and_runs_are_repeated(self) -> None:
        prompts = [{"id": "a", "prompt": "abcdef", "max_tokens": 3}, {"id": "b", "prompt": "xy"}]
        records = list(bench.run_benchmark(FakeEngine(), prompts, runs=2, label="t",
                                           default_max_tokens=5, metadata={}))

        self.assertEqual([(r["prompt_id"], r["run"]) for r in records],
                         [("a", 1), ("a", 2), ("b", 1), ("b", 2)])
        self.assertEqual(records[0]["text"], "abc")
        self.assertEqual(records[2]["completion_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
