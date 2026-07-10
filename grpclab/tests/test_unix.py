import asyncio
import contextlib
import tempfile
from pathlib import Path

from demo import demo_grpc, demo_pb2
from grpclab.example.server import Greeter
from grpclib.client import Channel
from grpclib.server import Server


def test_unix_socket():
    sock_path = tempfile.mktemp(suffix=".sock")

    async def run():
        server = Server([Greeter()])
        await server.start(path=sock_path)
        try:
            channel = Channel(path=sock_path)
            stub = demo_grpc.GreeterStub(channel)
            response = await stub.SayHello(demo_pb2.HelloRequest(name="Test"))
            assert response.message == "Hello, Test!"
            channel.close()
        finally:
            server.close()
            await server.wait_closed()

    try:
        asyncio.run(run())
    finally:
        with contextlib.suppress(OSError):
            Path(sock_path).unlink()
