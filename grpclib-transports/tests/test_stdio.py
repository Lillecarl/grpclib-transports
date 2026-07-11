import asyncio
import sys

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports.stdio import stdio_worker


async def test_stdio_transport() -> None:
    async with stdio_worker(
        [sys.executable, "-m", "grpclib_transports", "server", "--stdio"],
        stderr=asyncio.subprocess.PIPE,
    ) as channel:
        stub = greeter_grpc.GreeterStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="Stdio"))
        assert response.message == "Hello, Stdio!"
