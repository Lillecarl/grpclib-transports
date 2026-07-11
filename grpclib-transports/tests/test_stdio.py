import asyncio
import sys

from demo import demo_grpc, demo_pb2
from grpclib_transports.stdio import stdio_worker


def test_stdio_transport():
    async def run():
        async with stdio_worker(
            [sys.executable, "-m", "grpclib_transports", "server", "--stdio"],
            stderr=asyncio.subprocess.PIPE,
        ) as channel:
            stub = demo_grpc.GreeterStub(channel)
            response = await stub.SayHello(demo_pb2.HelloRequest(name="Stdio"))
            assert response.message == "Hello, Stdio!"

    asyncio.run(run())
