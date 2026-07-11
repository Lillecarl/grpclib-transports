import asyncio
import contextlib
import os
import tempfile
from pathlib import Path

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports.client import connect_unix
from grpclib_transports.example.server import Greeter
from grpclib_transports.server import Server


def test_unix_socket():
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    Path(sock_path).unlink()

    async def run():
        server = Server([Greeter()])
        await server.start_unix(sock_path)
        try:
            channel = connect_unix(sock_path)
            stub = greeter_grpc.GreeterStub(channel)
            response = await stub.SayHello(greeter_pb2.HelloRequest(name="Test"))
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
