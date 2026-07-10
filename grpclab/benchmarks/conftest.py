from __future__ import annotations

import asyncio
import contextlib
import fcntl
import io
import os
import re
import statistics
import time
import traceback
from pathlib import Path

import grpclab._logging  # noqa: F401
from demo import demo_grpc, demo_pb2
from grpclab.protocol import DEFAULT_TUNING


def _bump_pipe_buf(proc: asyncio.subprocess.Process) -> None:
    """Increase kernel pipe buffer size on subprocess pipes."""
    popen = getattr(getattr(proc, "_transport", None), "_proc", None)
    if popen is None:
        return
    for attr in ("stdin", "stdout", "stderr"):
        f = getattr(popen, attr, None)
        if f is not None:
            with contextlib.suppress(OSError):
                fcntl.fcntl(f.fileno(), fcntl.F_SETPIPE_SZ, DEFAULT_TUNING.buffer_size)

SMALL_COUNT = 200
LARGE_COUNT = 5
LARGE_SIZE = 1024 * 1024
SMALL_PAYLOAD = b""
LARGE_PAYLOAD = os.urandom(LARGE_SIZE)

DUMP_DIR = Path.cwd() / ".bench-dumps"
DUMP_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30
BENCH_SAMPLES = 3
PROFILE_BENCHMARKS = os.environ.get("GRPCLAB_BENCH_PROFILE") == "1"

_bench_results: list[dict] = []
_dump_paths: list[Path] = []


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


async def _bench_once(stub, req, count, parallelism=1):
    start = 0.0

    if parallelism == 1:
        for i in range(count + 1):
            await stub.SayHello(req)
            if i == 0:
                start = time.perf_counter()
    else:
        warmup = [asyncio.create_task(stub.SayHello(req)) for _ in range(parallelism)]
        await asyncio.gather(*warmup)

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
    samples = [
        await _bench_once(stub, req, count, parallelism=parallelism)
        for _ in range(BENCH_SAMPLES)
    ]
    elapsed = statistics.median(samples)
    _report(label, count, elapsed, len(payload), samples)


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
    return f"{v:>10.0f} msgs/s"


def _fmt_mb(v: float) -> str:
    return f"{v:>10.2f} MB/s"


def _fmt_spread(sample_rates: list[float]) -> str:
    high = max(sample_rates)
    low = min(sample_rates)
    median = statistics.median(sample_rates)
    if median == 0:
        return f"{'0.0%':>14}"
    return f"{((high - low) / median * 100):>13.1f}%"


def pytest_terminal_summary(terminalreporter, exitstatus, config):  # noqa: ARG001
    if not _bench_results:
        # Even if no results, print dump paths if we have them
        if _dump_paths:
            terminalreporter.section("Diagnostic Dumps", bold=True, yellow=True)
            for p in _dump_paths:
                terminalreporter.write_line(f"  {p}")
        return

    terminalreporter.section("Benchmark Summary", bold=True, blue=True)

    for test_type in ("small", "large"):
        rows = [r for r in _bench_results if r["type"] == test_type]
        if not rows:
            continue

        transports = sorted({r["transport"] for r in rows})
        parallelisms = sorted({r["parallelism"] for r in rows})

        heading = f"{test_type.upper()} ({rows[0]['count']} x {rows[0]['payload_size']} B)"
        terminalreporter.write_line(f"\n{heading}\n")

        header = f"{'Transport':<12}" + "".join(f"  {f'p={p}':>14}" for p in parallelisms)
        terminalreporter.write_line(header)
        terminalreporter.write_line("-" * len(header))

        for t in transports:
            line = f"{t:<12}"
            for p in parallelisms:
                match = next((r for r in rows if r["transport"] == t and r["parallelism"] == p), None)
                if match:
                    fmt = _fmt_mb if match["payload_size"] else _fmt_msgs
                    line += "  " + fmt(match["mb_per_sec"] if match["payload_size"] else match["msgs_per_sec"])
                else:
                    line += f"  {'N/A':>14}"
            terminalreporter.write_line(line)

    terminalreporter.section("Benchmark Spread", bold=True, blue=True)
    terminalreporter.write_line(
        f"Relative sample range across {BENCH_SAMPLES} samples; lower is steadier."
    )

    for test_type in ("small", "large"):
        rows = [r for r in _bench_results if r["type"] == test_type]
        if not rows:
            continue

        transports = sorted({r["transport"] for r in rows})
        parallelisms = sorted({r["parallelism"] for r in rows})

        terminalreporter.write_line(f"\n{test_type.upper()}\n")
        header = f"{'Transport':<12}" + "".join(f"  {f'p={p}':>14}" for p in parallelisms)
        terminalreporter.write_line(header)
        terminalreporter.write_line("-" * len(header))

        for t in transports:
            line = f"{t:<12}"
            for p in parallelisms:
                match = next((r for r in rows if r["transport"] == t and r["parallelism"] == p), None)
                if match:
                    line += "  " + _fmt_spread(match["sample_rates"])
                else:
                    line += f"  {'N/A':>14}"
            terminalreporter.write_line(line)

    if _dump_paths:
        terminalreporter.section("Diagnostic Dumps", bold=True, yellow=True)
        terminalreporter.write_line(f"  Dump directory: {DUMP_DIR}")
        terminalreporter.write_line("")
        for p in _dump_paths:
            terminalreporter.write_line(f"  {p}")
