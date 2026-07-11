import contextlib
import os
import tempfile
from pathlib import Path

from greeter import greeter_grpc, greeter_pb2
from grpclib_transports.client import connect_unix
from grpclib_transports.example.server import Greeter
from grpclib_transports.server import Server


async def test_unix_socket() -> None:
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    Path(sock_path).unlink()

    try:
        async with Server() as server:
            await server.endpoint([Greeter()]).listen_unix(sock_path)
            channel = connect_unix(sock_path)
            try:
                stub = greeter_grpc.GreeterStub(channel)
                response = await stub.SayHello(greeter_pb2.HelloRequest(name="Test"))
                assert response.message == "Hello, Test!"
            finally:
                channel.close()
    finally:
        with contextlib.suppress(OSError):
            Path(sock_path).unlink()
