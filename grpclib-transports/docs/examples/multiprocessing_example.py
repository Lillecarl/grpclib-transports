"""Multiprocessing transport — forkserver worker speaks gRPC over OS pipes.

Run with::

    python docs/examples/multiprocessing_example.py
"""

from __future__ import annotations

import asyncio

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports import Server
from grpclib_transports.example.server import Greeter


def worker_services() -> list[Greeter]:
    return [Greeter()]


async def main() -> None:
    async with Server() as server:
        workers = server.endpoint([]).for_workers()

        async with workers.multiprocessing_channels(
            worker_services,
            client_factory=greeter_grpc.GreeterStub,
            preload=["greeter"],
        ) as pool:
            stub = pool[0].client
            response = await stub.SayHello(greeter_pb2.HelloRequest(name="Multiprocessing"))
            assert response.message == "Hello, Multiprocessing!"
            print(f"Greeter replied: {response.message}")


if __name__ == "__main__":
    asyncio.run(main())
