from __future__ import annotations

import asyncio
import contextlib
import os
import statistics
import sys
import tempfile
import time

import anyio
import pytest
from conftest import BENCH_SAMPLES, _bump_pipe_buf, _report, _run
from demo import demo_grpc, demo_pb2
from grpclab.protocol import DEFAULT_TUNING, iter_chunks, make_config
from grpclab.stdio import StdioChannel
from grpclib.client import Channel

TOTAL_SIZE = 8 * 1024 * 1024
UPLOAD_COUNT = 2
UPLOAD_DATA = os.urandom(TOTAL_SIZE)
UPLOAD_MESSAGES = [
    demo_pb2.HelloRequest(name="chunk", payload=chunk)
    for chunk in iter_chunks(UPLOAD_DATA, DEFAULT_TUNING.transfer_chunk_size)
]


async def _upload_once(stub) -> None:
    response = await stub.Upload(UPLOAD_MESSAGES)
    assert response.message == f"Uploaded {TOTAL_SIZE} bytes"


async def _bench_upload(label, channel) -> None:
    stub = demo_grpc.GreeterStub(channel)
    await _upload_once(stub)

    samples = []
    for _ in range(BENCH_SAMPLES):
        start = time.monotonic()
        for _ in range(UPLOAD_COUNT):
            await _upload_once(stub)
        samples.append(time.monotonic() - start)

    _report(
        label,
        UPLOAD_COUNT,
        statistics.median(samples),
        TOTAL_SIZE,
        samples,
    )


@pytest.mark.parametrize("transport", ["stdio", "unixproc"])
def test_streaming_upload_8mib(transport):
    async def run_stdio():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "grpclab", "server", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _bump_pipe_buf(proc)
        channel = StdioChannel(proc.stdout, proc.stdin)
        try:
            await _bench_upload("stdio (stream8MiB, p=1)", channel)
        finally:
            await channel.aclose()
            proc.kill()
            if proc.stderr is not None:
                await asyncio.wait_for(proc.stderr.read(), timeout=3)
            await proc.wait()

    async def run_unixproc():
        sock = tempfile.mktemp(suffix=".sock")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "grpclab",
            "server",
            "--unix-path",
            sock,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        channel = None
        try:
            for _ in range(100):
                if await anyio.Path(sock).exists():
                    break
                await asyncio.sleep(0.01)
            channel = Channel(path=sock, config=make_config())
            await _bench_upload("unixproc (stream8MiB, p=1)", channel)
        finally:
            if channel is not None:
                channel.close()
            proc.kill()
            if proc.stderr is not None:
                await asyncio.wait_for(proc.stderr.read(), timeout=3)
            await proc.wait()
            with contextlib.suppress(OSError):
                await anyio.Path(sock).unlink()

    if transport == "stdio":
        _run("stdio (stream8MiB, p=1)", run_stdio())
    else:
        _run("unixproc (stream8MiB, p=1)", run_unixproc())
