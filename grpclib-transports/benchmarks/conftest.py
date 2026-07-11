from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import statistics
import time
import traceback
from pathlib import Path

from demo import demo_grpc, demo_pb2
from grpclib_transports.protocol import DEFAULT_TUNING
from grpclib_transports.stdio import _bump_subprocess_pipe_buffers
from rich.console import Console
from rich.table import Table

logging.getLogger("h2").setLevel(logging.WARNING)
logging.getLogger("asyncssh").setLevel(logging.WARNING)


def _bump_pipe_buf(proc: asyncio.subprocess.Process) -> None:
    """Increase kernel pipe buffer size on subprocess pipes."""
    _bump_subprocess_pipe_buffers(proc, tuning=DEFAULT_TUNING)

SMALL_COUNT = 200
LARGE_COUNT = 5
LARGE_SIZE = 1024 * 1024
SMALL_PAYLOAD = b""
LARGE_PAYLOAD = os.urandom(LARGE_SIZE)

DUMP_DIR = Path.cwd() / ".bench-dumps"
DUMP_DIR.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer") from e
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


TIMEOUT = _env_int("GRPCLAB_BENCH_TIMEOUT", 30)
BENCH_SAMPLES = _env_int("GRPCLAB_BENCH_SAMPLES", 3)
STARTUP_COUNT = _env_int("GRPCLAB_BENCH_STARTUP_COUNT", 3)
PROFILE_BENCHMARKS = os.environ.get("GRPCLAB_BENCH_PROFILE") == "1"

_bench_results: list[dict] = []
_latency_results: list[dict] = []
_dump_paths: list[Path] = []


def _bench_types() -> list[str]:
    preferred = ["small", "large"]
    seen = {r["type"] for r in _bench_results}
    return [t for t in preferred if t in seen] + sorted(seen - set(preferred))


def _sample_rate(count, elapsed, payload_size):
    if payload_size:
        return count * payload_size / elapsed / (1024 * 1024)
    return count / elapsed


def _report(label, count, elapsed, payload_size, samples):
    msgs_per_sec = count / elapsed
    total_bytes = count * payload_size
    mb_per_sec = total_bytes / elapsed / (1024 * 1024)
    if payload_size:
        pass

    m = re.match(r"(\w+) \((\w+), p=(\d+)\)", label)
    if m:
        _bench_results.append({
            "transport": m.group(1),
            "type": m.group(2),
            "parallelism": int(m.group(3)),
            "count": count,
            "elapsed": elapsed,
            "payload_size": payload_size,
            "msgs_per_sec": msgs_per_sec,
            "mb_per_sec": mb_per_sec,
            "sample_rates": [
                _sample_rate(count, sample, payload_size)
                for sample in samples
            ],
        })


def _report_latency(label, count, elapsed, samples):
    m = re.match(r"(\w+) \((\w+)\)", label)
    if m:
        _latency_results.append({
            "transport": m.group(1),
            "type": m.group(2),
            "count": count,
            "elapsed": elapsed,
            "ms_per_op": elapsed / count * 1000,
            "sample_ms_per_op": [
                sample / count * 1000
                for sample in samples
            ],
        })


def _dump_tasks(label: str, loop: asyncio.AbstractEventLoop) -> Path:
    """Dump all asyncio task stacks to a file, return the file path."""
    safe = re.sub(r"[^\w.]", "_", label)
    path = DUMP_DIR / f"{safe}_tasks.txt"
    buf = io.StringIO()
    buf.write(f"=== Task stack dump for '{label}' at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    tasks = asyncio.all_tasks(loop)
    buf.write(f"Total tasks: {len(tasks)}\n\n")
    for i, task in enumerate(sorted(tasks, key=lambda t: t.get_name())):
        buf.write(f"--- Task {i}: {task.get_name()} done={task.done()} ---\n")
        task.print_stack(file=buf)
        buf.write("\n")
    content = buf.getvalue()
    with path.open("w") as f:
        f.write(content)
    # Print a brief summary to stderr/stdout
    # Print the first 60 lines inline so it shows up in -s mode
    for _line in content.splitlines()[:60]:
        pass
    _dump_paths.append(path)
    return path


def _dump_profile(label: str, path_to_timeline: str) -> Path:
    """Write the pyinstrument pathToTimeline to a text file, return the file path."""
    safe = re.sub(r"[^\w.]", "_", label)
    path = DUMP_DIR / f"{safe}_profile.txt"
    with path.open("w") as f:
        f.write(path_to_timeline)
    _dump_paths.append(path)
    return path


async def _bench_warmup(stub, req, parallelism=1):
    if parallelism == 1:
        await stub.SayHello(req)
    else:
        warmup = [asyncio.create_task(stub.SayHello(req)) for _ in range(parallelism)]
        await asyncio.gather(*warmup)


async def _bench_once(stub, req, count, parallelism=1):
    if parallelism == 1:
        start = time.perf_counter()
        for _ in range(count):
            await stub.SayHello(req)
        return time.perf_counter() - start

    q: asyncio.Queue[None] = asyncio.Queue()
    for _ in range(count):
        q.put_nowait(None)

    async def worker():
        while True:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                return
            await stub.SayHello(req)

    start = time.perf_counter()
    workers = [asyncio.create_task(worker()) for _ in range(parallelism)]
    await asyncio.gather(*workers)
    return time.perf_counter() - start


async def _bench(label, payload, count, channel, parallelism=1):
    stub = demo_grpc.GreeterStub(channel)
    req = demo_pb2.HelloRequest(name="bench", payload=payload)
    await _bench_warmup(stub, req, parallelism=parallelism)
    samples = [
        await _bench_once(stub, req, count, parallelism=parallelism)
        for _ in range(BENCH_SAMPLES)
    ]
    elapsed = statistics.median(samples)
    _report(label, count, elapsed, len(payload), samples)


async def _bench_lifecycle(label, count, operation):
    samples = []
    for _ in range(BENCH_SAMPLES):
        start = time.perf_counter()
        for _ in range(count):
            await operation()
        samples.append(time.perf_counter() - start)
    elapsed = statistics.median(samples)
    _report_latency(label, count, elapsed, samples)


async def _runner_with_timeout(coro, label, loop):
    """
    Run coro with a manual timeout. On timeout, dump task stacks *before*
    cancelling anything, so we capture the true deadlock state.
    """
    main_task = asyncio.ensure_future(coro, loop=loop)
    timed_out = False

    def _on_timeout():
        nonlocal timed_out
        timed_out = True
        _dump_tasks(label, loop)
        main_task.cancel()

    timer = loop.call_later(TIMEOUT, _on_timeout)
    try:
        await main_task
    except asyncio.CancelledError:
        if timed_out:
            raise TimeoutError from None
        raise
    finally:
        timer.cancel()


def _run_with_dump(label, coro_factory):
    """
    Run a benchmark with full profiling support.

    coro_factory: a zero-arg callable that returns a fresh coroutine.
    We need a factory because we might need to re-create the coroutine.

    On success: dump pyinstrument profile.
    On timeout: dump all asyncio task stacks from the event loop *before*
    cancelling, so we capture the true deadlock state.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    profiler = None
    if PROFILE_BENCHMARKS:
        from pyinstrument import Profiler

        profiler = Profiler(interval=0.001)
        profiler.start()

    coro = coro_factory()
    wrapper = _runner_with_timeout(coro, label, loop)

    try:
        loop.run_until_complete(wrapper)
    except TimeoutError:
        raise  # already dumped tasks in _on_timeout
    except Exception:
        traceback.print_exc()
        _dump_tasks(label, loop)
        raise
    finally:
        if profiler is not None:
            profiler.stop()
            try:
                profile_text = profiler.output_text(unicode=True, color=False, show_all=True)
            except Exception:
                profile_text = "Failed to generate pyinstrument text output"
            _dump_profile(label, profile_text)

        # Cancel any remaining tasks
        pending = asyncio.all_tasks(loop)
        for t in pending:
            t.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


def _run(label, coro):
    """
    Run a benchmark with profiling and task-stack dump on timeout.
    Accepts a coroutine (not a factory) — wraps it for _run_with_dump.
    """
    _run_with_dump(label, lambda: coro)


def _fmt_msgs(v: float) -> str:
    return f"{v:,.0f} msgs/s"


def _fmt_mb(v: float) -> str:
    return f"{v:,.2f} MB/s"


def _fmt_spread(sample_rates: list[float]) -> str:
    high = max(sample_rates)
    low = min(sample_rates)
    median = statistics.median(sample_rates)
    if median == 0:
        return "0.0%"
    return f"{(high - low) / median * 100:.1f}%"


def _fmt_ms(v: float) -> str:
    return f"{v:,.2f} ms"


_console = Console(highlight=False)


def _build_throughput_table(test_type: str, rows: list[dict]) -> Table:
    transports = sorted({r["transport"] for r in rows})
    parallelisms = sorted({r["parallelism"] for r in rows})
    cols = ["Transport"] + [f"p={p}" for p in parallelisms]
    heading = f"{test_type.upper()} ({rows[0]['count']} x {rows[0]['payload_size']} B)"
    table = Table(*cols, title=heading)
    table.columns[0].no_wrap = True
    table.columns[0].min_width = max(len(t) for t in transports)
    for col in table.columns[1:]:
        col.no_wrap = True
    for t in transports:
        vals: list[str] = [t]
        for p in parallelisms:
            match = next(
                (r for r in rows if r["transport"] == t and r["parallelism"] == p), None
            )
            if match:
                if match["payload_size"]:
                    thr = _fmt_mb(match["mb_per_sec"])
                else:
                    thr = _fmt_msgs(match["msgs_per_sec"])
                spread = _fmt_spread(match["sample_rates"])
                vals.append(f"{thr}\n{spread}")
            else:
                vals.append("N/A")
        table.add_row(*vals)
    return table


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    if not _bench_results and not _latency_results:
        if _dump_paths:
            terminalreporter.section("Diagnostic Dumps", bold=True, yellow=True)
            for p in _dump_paths:
                terminalreporter.write_line(f"  {p}")
        return

    if _bench_results:
        mainstream = [r for r in _bench_results if r["type"] in ("small", "large")]
        sweep = [r for r in _bench_results if r["type"] not in ("small", "large")]

        for test_type in _bench_types():
            rows = [r for r in mainstream if r["type"] == test_type]
            if not rows:
                continue
            _console.print()
            _console.print(_build_throughput_table(test_type, rows))

        if sweep:
            _console.print()
            table = Table("Transport", "Throughput", "Spread", title="PAYLOAD SWEEP & STREAMING")
            for r in sorted(sweep, key=lambda r: (r["transport"], r["type"])):
                fmt = _fmt_mb if r["payload_size"] else _fmt_msgs
                val = r["mb_per_sec"] if r["payload_size"] else r["msgs_per_sec"]
                table.add_row(
                    f"{r['transport']}  {r['type']}",
                    fmt(val),
                    _fmt_spread(r["sample_rates"]),
                )
            _console.print(table)

    if _latency_results:
        _console.print()
        table = Table("Transport", "median", "spread")
        for test_type in sorted({r["type"] for r in _latency_results}):
            rows = [r for r in _latency_results if r["type"] == test_type]
            heading = f"{test_type.upper()} ({rows[0]['count']} workers/sample)"
            table.add_section()
            table.columns[0].header = heading
            for row in sorted(rows, key=lambda r: r["transport"]):
                table.add_row(
                    row["transport"],
                    _fmt_ms(row["ms_per_op"]),
                    _fmt_spread(row["sample_ms_per_op"]),
                )
        _console.print(table)

    if _dump_paths:
        terminalreporter.section("Diagnostic Dumps", bold=True, yellow=True)
        terminalreporter.write_line(f"  Dump directory: {DUMP_DIR}")
        terminalreporter.write_line("")
        for p in _dump_paths:
            terminalreporter.write_line(f"  {p}")
