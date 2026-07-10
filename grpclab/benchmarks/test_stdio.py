import asyncio
import sys

import pytest

from conftest import SMALL_PAYLOAD, LARGE_PAYLOAD, SMALL_COUNT, LARGE_COUNT, _bench, _run

from grpclab.stdio import StdioChannel


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_stdio(parallelism):
    async def run():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "grpclab", "server", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        channel = StdioChannel(proc.stdout, proc.stdin)
        try:
            await _bench(f"stdio (small, p={parallelism})", SMALL_PAYLOAD, SMALL_COUNT, channel, parallelism=parallelism)
            await _bench(f"stdio (large, p={parallelism})", LARGE_PAYLOAD, LARGE_COUNT, channel, parallelism=parallelism)
        finally:
            channel.close()
            proc.kill()
            serr = await asyncio.wait_for(proc.stderr.read(), timeout=3)
            if serr:
                print(f"  [server stderr] {serr.decode()[:200]}")
    _run(f"stdio (p={parallelism})", run())
