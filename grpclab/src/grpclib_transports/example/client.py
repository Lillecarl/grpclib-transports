from __future__ import annotations

from typing import Any

from demo import demo_grpc, demo_pb2

from grpclib_transports.client import connect_unix
from grpclib_transports.ssh import connect_ssh
from grpclib_transports.stdio import StdioChannel, _stdio_streams


async def greet(channel: Any, name: str = "World") -> None:
    stub = demo_grpc.GreeterStub(channel)
    request = demo_pb2.HelloRequest(name=name)
    await stub.SayHello(request)


async def greet_unix(path: str, name: str = "World") -> None:
    async with connect_unix(path) as channel:
        await greet(channel, name)


async def greet_stdio(name: str = "World") -> None:
    reader, writer, transport = await _stdio_streams()
    channel = StdioChannel(reader, writer, transport=transport)
    try:
        await greet(channel, name)
    finally:
        channel.close()


async def greet_ssh(
    host: str = "127.0.0.1",
    port: int = 8022,
    username: str = "demo",
    password: str = "demo",
    name: str = "World",
) -> None:
    async with connect_ssh(
        host,
        port,
        username=username,
        password=password,
        known_hosts=None,
    ) as channel:
        await greet(channel, name)
