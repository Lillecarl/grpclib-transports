"""Multiprocessing transport — forkserver worker speaks gRPC over OS pipes.

Run with::

    python docs/examples/multiprocessing_example.py
"""

from __future__ import annotations

import asyncio

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports.example.server import Greeter
from grpclib_transports.multiprocessing import multiprocessing_worker


def worker_services() -> list[Greeter]:
    return [Greeter()]


async def main() -> None:
    async with multiprocessing_worker(worker_services, preload=["greeter"]) as channel:
        stub = greeter_grpc.GreeterStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="Multiprocessing"))
        assert response.message == "Hello, Multiprocessing!"
        print(f"Greeter replied: {response.message}")


if __name__ == "__main__":
    asyncio.run(main())
