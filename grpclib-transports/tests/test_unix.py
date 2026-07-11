from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
from typing import Any

from anyio import Path
from greeter import common_pb2, server_grpc
from grpclib_transports.client import connect_unix
from grpclib_transports.example.server import Greeter
from grpclib_transports.server import Server


class _BlockingGreeter(server_grpc.GreeterBase):
    def __init__(self) -> None:
        self.first_entered = asyncio.Event()
        self.release_first = asyncio.Event()
        self.started = 0
        self.active = 0
        self.max_active = 0

    async def SayHello(self, stream: Any) -> None:  # noqa: N802 -- gRPC method name from protobuf
        request = await stream.recv_message()
        if request is None:
            return
        self.started += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.started == 1:
            self.first_entered.set()
            await self.release_first.wait()
        self.active -= 1
        await stream.send_message(common_pb2.HelloReply(message=f"Hello, {request.name}!"))

    async def Upload(self, stream: Any) -> None:  # noqa: N802 -- gRPC method name from protobuf
        await stream.send_message(common_pb2.HelloReply(message="unused"))


async def test_unix_socket() -> None:
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    await Path(sock_path).unlink()

    try:
        async with Server() as server:
            await server.endpoint([Greeter()]).listen_unix(sock_path)
            channel = connect_unix(sock_path)
            try:
                stub = server_grpc.GreeterStub(channel)
                response = await stub.SayHello(common_pb2.HelloRequest(name="Test"))
                assert response.message == "Hello, Test!"
            finally:
                channel.close()
    finally:
        with contextlib.suppress(OSError):
            await Path(sock_path).unlink()


async def test_endpoint_max_concurrency_limits_handler_entry() -> None:
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    await Path(sock_path).unlink()
    greeter = _BlockingGreeter()

    try:
        async with Server() as server:
            await server.endpoint([greeter], max_concurrency=1).listen_unix(sock_path)
            channel = connect_unix(sock_path)
            try:
                stub = server_grpc.GreeterStub(channel)
                first = asyncio.create_task(
                    stub.SayHello(common_pb2.HelloRequest(name="First")),
                    name="first-limited-rpc",
                )
                second = asyncio.create_task(
                    stub.SayHello(common_pb2.HelloRequest(name="Second")),
                    name="second-limited-rpc",
                )
                await greeter.first_entered.wait()
                await asyncio.sleep(0.05)
                assert greeter.started == 1
                assert greeter.max_active == 1
                greeter.release_first.set()
                responses = await asyncio.gather(first, second)
                assert [response.message for response in responses] == [
                    "Hello, First!",
                    "Hello, Second!",
                ]
            finally:
                channel.close()
    finally:
        with contextlib.suppress(OSError):
            await Path(sock_path).unlink()
