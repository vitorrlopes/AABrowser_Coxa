"""Implementação de referência do Problema B — valida a própria suíte oculta.

NÃO enviar este arquivo aos modelos avaliados.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class TokenBucket:
    def __init__(self, capacity: float, refill_per_second: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if capacity <= 0:
            raise ValueError("capacity deve ser > 0")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second deve ser > 0")
        self._capacity = float(capacity)
        self._rate = float(refill_per_second)
        self._clock = clock
        self._tokens = self._capacity
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last)  # relógio que volta não gera tokens
        self._last = max(self._last, now)
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)

    def try_acquire(self, tokens: float = 1) -> bool:
        if tokens <= 0 or tokens > self._capacity:
            raise ValueError("tokens deve estar em (0, capacity]")
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens
