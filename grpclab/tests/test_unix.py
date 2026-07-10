import asyncio
import tempfile
import os
import socket

from demo import demo_grpc, demo_pb2
from grpclab.example.server import Greeter
from grpclib.server import Server
from grpclib.client import Channel


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
        try:
            os.unlink(sock_path)
        except OSError:
            pass
