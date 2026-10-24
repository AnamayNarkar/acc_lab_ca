"""Shared request logic for EC2 server and Lambda handler.
/work?ms=N&cpu=C : total service time N ms, of which C ms is calibrated single-core CPU burn, rest is sleep (I/O wait)."""
import time

def _calibrate():
    t = time.perf_counter(); n = 0; x = 1
    while time.perf_counter() - t < 0.15:
        for _ in range(2000): x = (x * 1103515245 + 12345) & 0xFFFFFFFF
        n += 2000
    return n / ((time.perf_counter() - t) * 1000.0)  # iterations per ms
ITERS_PER_MS = _calibrate()

def burn(cpu_ms):
    n = int(cpu_ms * ITERS_PER_MS); x = 1
    for _ in range(n): x = (x * 1103515245 + 12345) & 0xFFFFFFFF
    return x

def do_work(ms, cpu):
    t0 = time.perf_counter()
    cpu = min(cpu, ms)
    burn(cpu)
    rest = ms / 1000.0 - (time.perf_counter() - t0)
    if rest > 0: time.sleep(rest)
    return (time.perf_counter() - t0) * 1000.0
