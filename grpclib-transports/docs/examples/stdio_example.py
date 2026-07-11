"""Stdio transport — subprocess server + client over stdin/stdout.

Run with::

    python docs/examples/stdio_example.py
"""

from __future__ import annotations

import asyncio

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports import stdio_worker


async def main() -> None:
    import sys

    async with stdio_worker(
        [sys.executable, "-m", "grpclib_transports", "server", "--stdio"],
        stderr=asyncio.subprocess.PIPE,
    ) as channel:
        stub = greeter_grpc.GreeterStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="Stdio"))
        assert response.message == "Hello, Stdio!"
        print(f"Greeter replied: {response.message}")


if __name__ == "__main__":
    asyncio.run(main())
