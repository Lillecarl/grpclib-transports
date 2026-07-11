from __future__ import annotations

import contextlib
import os
import tempfile

from anyio import Path

import greeter.greeter.common as common_pb2
import greeter.greeter.server as server_grpc
from greeter.greeter.common import HelloReply, HelloRequest
from grpclib_transports.client import connect_unix
from grpclib_transports.example.server import Greeter
from grpclib_transports.monkey_patcher import MonkeyPatcher
from grpclib_transports.server import Server


class HelloRequestExt(HelloRequest, MonkeyPatcher):
    @property
    def upper_name(self) -> str:
        return self.name.upper()

    @property
    def lower_name(self) -> str:
        return self.name.lower()


class HelloReplyExt(HelloReply, MonkeyPatcher):
    @property
    def upper_message(self) -> str:
        return self.message.upper()

    @property
    def lower_message(self) -> str:
        return self.message.lower()


async def test_monkey_patcher_replaces_class_in_module() -> None:
    assert common_pb2.HelloRequest is HelloRequestExt
    assert common_pb2.HelloReply is HelloReplyExt


async def test_monkey_patcher_deserialization_produces_patched_instance() -> None:
    request = HelloRequestExt(name="WorLd")
    data = bytes(request)
    deserialized = common_pb2.HelloRequest.parse(data)
    assert isinstance(deserialized, HelloRequestExt)
    assert deserialized.upper_name == "WORLD"
    assert deserialized.lower_name == "world"

    reply = HelloReplyExt(message="Hello, WorLd!")
    data = bytes(reply)
    deserialized = common_pb2.HelloReply.parse(data)
    assert isinstance(deserialized, HelloReplyExt)
    assert deserialized.upper_message == "HELLO, WORLD!"
    assert deserialized.lower_message == "hello, world!"


async def test_monkey_patcher_rpc_round_trip() -> None:
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    await Path(sock_path).unlink()

    try:
        async with Server() as server:
            await server.endpoint([Greeter()]).listen_unix(sock_path)
            channel = connect_unix(sock_path)
            try:
                stub = server_grpc.GreeterStub(channel)
                response = await stub.say_hello(common_pb2.HelloRequest(name="WorLd"))
                assert isinstance(response, HelloReplyExt)
                assert response.upper_message == "HELLO, WORLD!"
                assert response.lower_message == "hello, world!"
            finally:
                channel.close()
    finally:
        with contextlib.suppress(OSError):
            await Path(sock_path).unlink()
