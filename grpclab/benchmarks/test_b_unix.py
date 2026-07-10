import contextlib
import tempfile

import anyio
import pytest
from conftest import LARGE_COUNT, LARGE_PAYLOAD, SMALL_COUNT, SMALL_PAYLOAD, _bench, _run
from grpclab.example.server import Greeter
from grpclab.protocol import make_config
from grpclib.client import Channel
from grpclib.server import Server as GrpcServer


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
