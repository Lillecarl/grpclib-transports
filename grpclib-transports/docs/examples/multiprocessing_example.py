"""Multiprocessing transport — forked worker process speaks gRPC over OS pipes.

Run with::

    python docs/examples/multiprocessing_example.py
"""

from __future__ import annotations

import asyncio
import os

from greeter import greeter_grpc, greeter_pb2
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


async def main() -> None:
    pair = multiprocessing_pipe_pair(preload=["greeter"])

    proc = pair.context.Process(
        target=_serve_multiprocessing_worker,
        args=(pair.child,),
    )
    proc.start()
    pair.close_child_connections()

    channel = await pair.parent.open_channel()
    pair.close_parent_connections()

    try:
        stub = greeter_grpc.GreeterStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="Multiprocessing"))
        assert response.message == "Hello, Multiprocessing!"
        print(f"Greeter replied: {response.message}")
    finally:
        await channel.aclose()
        proc.terminate()
        await asyncio.to_thread(proc.join, 3)
        if proc.is_alive():
            proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
