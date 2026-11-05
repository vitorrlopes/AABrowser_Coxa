"""Suíte OCULTA do Problema B. Nunca mostrar aos modelos avaliados.

Uso:
    MANUTE_CANDIDATE=/caminho/solucao_modelo.py python3 -m unittest -v test_hidden
Sem a variável, roda contra a implementação de referência (autoteste da suíte).
"""
from __future__ import annotations

import importlib.util
import os
import threading
import unittest
from pathlib import Path

_DEFAULT = Path(__file__).with_name("reference_token_bucket.py")


def _load_candidate():
    path = Path(os.environ.get("MANUTE_CANDIDATE", _DEFAULT))
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TokenBucket


TokenBucket = _load_candidate()


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class ContractTest(unittest.TestCase):
    def make(self, capacity=5, rate=1.0):
        clock = FakeClock()
        return TokenBucket(capacity, rate, clock=clock), clock

    def test_starts_full_and_allows_burst_up_to_capacity(self):
        bucket, _ = self.make(capacity=3)
        self.assertEqual([bucket.try_acquire() for _ in range(4)], [True, True, True, False])

    def test_refills_proportionally_to_elapsed_time(self):
        bucket, clock = self.make(capacity=10, rate=2.0)
        self.assertTrue(bucket.try_acquire(10))
        clock.now += 1.5
        self.assertAlmostEqual(bucket.available(), 3.0)

    def test_never_exceeds_capacity(self):
        bucket, clock = self.make(capacity=4, rate=100.0)
        clock.now += 3600
        self.assertAlmostEqual(bucket.available(), 4.0)

    def test_failed_acquire_does_not_consume(self):
        bucket, _ = self.make(capacity=5)
        self.assertTrue(bucket.try_acquire(4))
        self.assertFalse(bucket.try_acquire(2))
        self.assertAlmostEqual(bucket.available(), 1.0)

    def test_multi_token_acquire(self):
        bucket, clock = self.make(capacity=5, rate=1.0)
        self.assertTrue(bucket.try_acquire(5))
        clock.now += 2.5
        self.assertTrue(bucket.try_acquire(2.5))
        self.assertFalse(bucket.try_acquire(0.5))

    def test_clock_going_backwards_does_not_add_tokens(self):
        bucket, clock = self.make(capacity=5, rate=1.0)
        self.assertTrue(bucket.try_acquire(5))
        clock.now -= 100
        self.assertAlmostEqual(bucket.available(), 0.0)
        clock.now += 100  # volta ao ponto original: ainda nada a recarregar
        self.assertAlmostEqual(bucket.available(), 0.0)

    def test_invalid_constructor_arguments(self):
        for capacity, rate in [(0, 1), (-1, 1), (1, 0), (1, -2)]:
            with self.subTest(capacity=capacity, rate=rate):
                with self.assertRaises(ValueError):
                    TokenBucket(capacity, rate, clock=FakeClock())

    def test_invalid_acquire_arguments(self):
        bucket, _ = self.make(capacity=5)
        for tokens in (0, -1, 6):
            with self.subTest(tokens=tokens):
                with self.assertRaises(ValueError):
                    bucket.try_acquire(tokens)

    def test_thread_safety_never_over_grants(self):
        bucket, _ = self.make(capacity=1000, rate=0.000001)
        granted = []
        lock = threading.Lock()

        def worker():
            count = sum(bucket.try_acquire() for _ in range(200))
            with lock:
                granted.append(count)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(granted), 1000)


if __name__ == "__main__":
    unittest.main()
