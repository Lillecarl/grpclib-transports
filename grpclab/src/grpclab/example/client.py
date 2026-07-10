from __future__ import annotations

from typing import Any

from demo import demo_grpc, demo_pb2
from grpclib.client import Channel

from grpclab.protocol import make_config
from grpclab.ssh import SshChannel
from grpclab.stdio import StdioChannel, _stdio_streams


async def greet(channel: Any, name: str = "World") -> None:
    stub = demo_grpc.GreeterStub(channel)
    request = demo_pb2.HelloRequest(name=name)
    await stub.SayHello(request)


async def greet_unix(path: str, name: str = "World") -> None:
    async with Channel(path=path, config=make_config()) as channel:
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
    import asyncssh

    async with asyncssh.connect(
        host,
        port,
        username=username,
        password=password,
        known_hosts=None,
    ) as conn:
        stdin, stdout, _stderr = await conn.open_session(encoding=None)
        channel = SshChannel(stdout, stdin)
        try:
            await greet(channel, name)
        finally:
            channel.close()
