#!/usr/bin/env python3
"""MANUTÊ — harness de benchmark reproduzível (Experimentos A, B e C).

Só usa a biblioteca padrão, para rodar igual no PC e no Termux (Android).

Fala com qualquer servidor compatível com o endpoint
`/v1/chat/completions` em streaming (ex.: `llama-server` do llama.cpp).
Mede TTFT e velocidade de decodificação e grava um registro JSONL por execução.

Por segurança, só aceita endpoints em loopback (127.0.0.1 / localhost / ::1).
Endpoints remotos exigem `--allow-remote`, para que nenhuma chamada externa
aconteça sem decisão explícita do usuário.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Protocol
from urllib.parse import urlparse

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class Generation:
    """Resultado de uma geração, independente do motor."""

    text: str
    ttft_s: float | None
    total_s: float
    completion_tokens: int
    tokens_source: str  # "server" (contagem real) ou "chunks" (estimativa)
    decode_tps: float | None
    prompt_tps: float | None = None


class Engine(Protocol):
    """Porta única que o CORE conhece. Trocar o motor = trocar o adaptador."""

    name: str

    def generate(self, prompt: str, *, max_tokens: int) -> Generation: ...


def ensure_allowed(base_url: str, allow_remote: bool) -> None:
    host = urlparse(base_url).hostname
    if host is None:
        raise ValueError(f"URL inválida: {base_url!r}")
    if host not in LOOPBACK_HOSTS and not allow_remote:
        raise PermissionError(
            f"Endpoint remoto {host!r} bloqueado. Use --allow-remote para autorizar."
        )


def iter_sse_data(lines: Iterable[bytes]) -> Iterator[dict]:
    """Extrai os objetos JSON das linhas `data:` de um stream SSE."""
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            return
        yield json.loads(payload)


@dataclass
class _StreamAccumulator:
    started: float
    parts: list[str] = field(default_factory=list)
    first_token_at: float | None = None
    content_chunks: int = 0
    usage_tokens: int | None = None
    timings: dict | None = None

    def feed(self, event: dict, now: float) -> None:
        for choice in event.get("choices") or []:
            content = (choice.get("delta") or {}).get("content")
            if content:
                if self.first_token_at is None:
                    self.first_token_at = now
                self.parts.append(content)
                self.content_chunks += 1
        if usage := event.get("usage"):
            self.usage_tokens = usage.get("completion_tokens", self.usage_tokens)
        if timings := event.get("timings"):  # extensão do llama-server
            self.timings = timings

    def result(self, finished: float) -> Generation:
        ttft = None if self.first_token_at is None else self.first_token_at - self.started
        if self.timings and self.timings.get("predicted_n"):
            tokens, source = int(self.timings["predicted_n"]), "server"
        elif self.usage_tokens is not None:
            tokens, source = self.usage_tokens, "server"
        else:
            tokens, source = self.content_chunks, "chunks"

        decode_tps = (self.timings or {}).get("predicted_per_second")
        if decode_tps is None and self.first_token_at is not None and tokens > 1:
            decode_window = finished - self.first_token_at
            decode_tps = (tokens - 1) / decode_window if decode_window > 0 else None

        return Generation(
            text="".join(self.parts),
            ttft_s=ttft,
            total_s=finished - self.started,
            completion_tokens=tokens,
            tokens_source=source,
            decode_tps=decode_tps,
            prompt_tps=(self.timings or {}).get("prompt_per_second"),
        )


class OpenAICompatibleEngine:
    """Adaptador para servidores locais compatíveis (llama-server, etc.)."""

    def __init__(self, base_url: str, model: str = "local", *, allow_remote: bool = False,
                 timeout_s: float = 600.0) -> None:
        ensure_allowed(base_url, allow_remote)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"openai-compatible:{model}"
        self.timeout_s = timeout_s

    def generate(self, prompt: str, *, max_tokens: int) -> Generation:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0,
            "stream": True,
            "stream_options": {"include_usage": True},
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        acc = _StreamAccumulator(started=time.perf_counter())
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            for event in iter_sse_data(response):
                acc.feed(event, time.perf_counter())
        return acc.result(time.perf_counter())


def load_prompts(path: Path) -> list[dict]:
    prompts = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not {"id", "prompt"} <= item.keys():
            raise ValueError(f"{path}:{number}: cada linha precisa de 'id' e 'prompt'")
        prompts.append(item)
    return prompts


def run_benchmark(engine: Engine, prompts: list[dict], *, runs: int, label: str,
                  default_max_tokens: int, metadata: dict) -> Iterator[dict]:
    for item in prompts:
        for run in range(1, runs + 1):
            generation = engine.generate(
                item["prompt"], max_tokens=int(item.get("max_tokens", default_max_tokens))
            )
            yield {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "label": label,
                "engine": engine.name,
                "prompt_id": item["id"],
                "run": run,
                **asdict(generation),
                "metadata": metadata,
            }


def summarize(records: list[dict]) -> dict[str, dict]:
    """Mediana por prompt — mediana porque o aparelho sofre throttling térmico."""
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["prompt_id"], []).append(record)

    def median_of(rows: list[dict], key: str) -> float | None:
        values = [row[key] for row in rows if row.get(key) is not None]
        return round(statistics.median(values), 3) if values else None

    return {
        prompt_id: {
            "runs": len(rows),
            "ttft_s_median": median_of(rows, "ttft_s"),
            "decode_tps_median": median_of(rows, "decode_tps"),
            "total_s_median": median_of(rows, "total_s"),
        }
        for prompt_id, rows in grouped.items()
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model", default="local", help="nome enviado ao servidor")
    parser.add_argument("--label", required=True, help="ex.: s22p-qwen3-1.7b-q4km-cpu")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--out", type=Path, required=True, help="arquivo JSONL (append)")
    parser.add_argument("--device-info", type=Path, help="saída de device_info.sh")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs deve ser >= 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    metadata = {}
    if args.device_info:
        metadata["device_info"] = args.device_info.read_text(encoding="utf-8")

    engine = OpenAICompatibleEngine(args.base_url, args.model, allow_remote=args.allow_remote)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with args.out.open("a", encoding="utf-8") as sink:
        for record in run_benchmark(engine, load_prompts(args.prompts), runs=args.runs,
                                    label=args.label, default_max_tokens=args.max_tokens,
                                    metadata=metadata):
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            sink.flush()  # não perder dados se o Android matar o processo
            records.append(record)
            print(f"{record['prompt_id']} run={record['run']} "
                  f"ttft={record['ttft_s']} tps={record['decode_tps']}", file=sys.stderr)

    print(json.dumps(summarize(records), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
