from __future__ import annotations

import asyncio
import os

import pytest
from conftest import LARGE_COUNT, LARGE_PAYLOAD, SMALL_COUNT, SMALL_PAYLOAD, _bench, _run
from grpclib_transports.example.server import Greeter
from grpclib_transports.multiprocessing import (
    MultiprocessingPipeEndpoint,
    multiprocessing_pipe_pair,
)
from grpclib_transports.pipes import pipe_streams_from_fds
from grpclib_transports.protocol import serve_h2


def _serve_multiprocessing_worker(endpoint: MultiprocessingPipeEndpoint) -> None:
    async def run() -> None:
        reader, _writer, transport = await pipe_streams_from_fds(
            os.dup(endpoint.read_connection.fileno()),
            os.dup(endpoint.write_connection.fileno()),
            transport_name="multiprocessing-worker",
        )
        endpoint.close_connections()
        await serve_h2([Greeter()], reader, transport)

    asyncio.run(run())


async def _stop_process(proc) -> None:
    if proc.is_alive():
        proc.terminate()
        await asyncio.to_thread(proc.join, 3)
    if proc.is_alive():
        proc.kill()
        await asyncio.to_thread(proc.join, 3)


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_multiprocessing(parallelism):
    async def run():
        pair = multiprocessing_pipe_pair()
        proc = pair.context.Process(
            target=_serve_multiprocessing_worker,
            args=(pair.child,),
        )
        proc.start()
        pair.close_child_connections()

        channel = await pair.parent.open_channel()
        pair.close_parent_connections()
        try:
            await _bench(
                f"multiprocessing (small, p={parallelism})",
                SMALL_PAYLOAD,
                SMALL_COUNT,
                channel,
                parallelism=parallelism,
            )
            await _bench(
                f"multiprocessing (large, p={parallelism})",
                LARGE_PAYLOAD,
                LARGE_COUNT,
                channel,
                parallelism=parallelism,
            )
        finally:
            await channel.aclose()
            await _stop_process(proc)

    _run(f"multiprocessing (p={parallelism})", run())
