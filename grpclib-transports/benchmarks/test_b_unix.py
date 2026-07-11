import asyncio
import contextlib
import sys
import tempfile

import anyio
import pytest
from conftest import LARGE_COUNT, LARGE_PAYLOAD, SMALL_COUNT, SMALL_PAYLOAD, _bench, _run
from grpclib.client import Channel
from grpclib.server import Server as GrpcServer
from grpclib_transports.example.server import Greeter
from grpclib_transports.protocol import make_config


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_unix(parallelism):
    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        server = GrpcServer([Greeter()], config=make_config())
        await server.start(path=sock)
        try:
            channel = Channel(path=sock, config=make_config())
            await _bench(f"unix (small, p={parallelism})", SMALL_PAYLOAD, SMALL_COUNT, channel, parallelism=parallelism)
            await _bench(f"unix (large, p={parallelism})", LARGE_PAYLOAD, LARGE_COUNT, channel, parallelism=parallelism)
            channel.close()
        finally:
            server.close()
            await server.wait_closed()
            with contextlib.suppress(OSError):
                await anyio.Path(sock).unlink()
    _run(f"unix (p={parallelism})", run())


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_unix_subprocess(parallelism):
    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "grpclib_transports",
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
            await _bench(f"unixproc (small, p={parallelism})", SMALL_PAYLOAD, SMALL_COUNT, channel, parallelism=parallelism)
            await _bench(f"unixproc (large, p={parallelism})", LARGE_PAYLOAD, LARGE_COUNT, channel, parallelism=parallelism)
        finally:
            if channel is not None:
                channel.close()
            proc.kill()
            if proc.stderr is not None:
                await asyncio.wait_for(proc.stderr.read(), timeout=3)
            await proc.wait()
            with contextlib.suppress(OSError):
                await anyio.Path(sock).unlink()
    _run(f"unixproc (p={parallelism})", run())
