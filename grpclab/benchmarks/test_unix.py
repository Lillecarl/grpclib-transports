import os
import tempfile

import pytest

from conftest import SMALL_PAYLOAD, LARGE_PAYLOAD, SMALL_COUNT, LARGE_COUNT, _bench, _run

from grpclab.server import Greeter
from grpclib.server import Server as GrpcServer
from grpclib.client import Channel


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_unix(parallelism):
    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        server = GrpcServer([Greeter()])
        await server.start(path=sock)
        try:
            channel = Channel(path=sock)
            await _bench(f"unix (small, p={parallelism})", SMALL_PAYLOAD, SMALL_COUNT, channel, parallelism=parallelism)
            await _bench(f"unix (large, p={parallelism})", LARGE_PAYLOAD, LARGE_COUNT, channel, parallelism=parallelism)
            channel.close()
        finally:
            server.close()
            await server.wait_closed()
            try:
                os.unlink(sock)
            except OSError:
                pass
    _run(f"unix (p={parallelism})", run())
