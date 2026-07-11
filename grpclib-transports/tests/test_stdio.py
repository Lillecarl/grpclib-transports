from __future__ import annotations

import asyncio
import sys

import greeter.greeter.common as common_pb2
import greeter.greeter.worker as worker_grpc
from grpclib_transports.stdio import stdio_worker


async def test_stdio_transport() -> None:
    async with stdio_worker(
        [sys.executable, "-m", "grpclib_transports", "server", "--stdio"],
        stderr=asyncio.subprocess.PIPE,
    ) as channel:
        stub = worker_grpc.GreeterWorkerStub(channel)
        response = await stub.say_hello(common_pb2.HelloRequest(name="Stdio"))
        assert response.message == "Hello, Stdio!"
