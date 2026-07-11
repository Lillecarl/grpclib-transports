"""Stdio transport — subprocess server + client over stdin/stdout.

Run with::

    python docs/examples/stdio_example.py
"""

from __future__ import annotations

import asyncio
import sys

from greeter import common_pb2, worker_grpc
from grpclib_transports import Server


async def main() -> None:
    async with Server() as server:
        workers = server.endpoint([]).for_workers()

        async with workers.stdio_channels(
            [
                sys.executable,
                "-m",
                "grpclib_transports",
                "server",
                "--stdio",
                "--max-concurrency",
                "1",
            ],
            client_factory=worker_grpc.GreeterWorkerStub,
            stderr=asyncio.subprocess.PIPE,
        ) as pool:
            stub = pool[0].client
            response = await stub.SayHello(common_pb2.HelloRequest(name="Stdio"))
            assert response.message == "Hello, Stdio!"
            print(f"Greeter replied: {response.message}")


if __name__ == "__main__":
    asyncio.run(main())
