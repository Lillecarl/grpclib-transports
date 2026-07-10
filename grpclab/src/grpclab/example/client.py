import sys
from typing import Any

from grpclib.client import Channel
from demo import demo_pb2, demo_grpc

from grpclab.stdio import StdioChannel, _stdio_streams
from grpclab.ssh import SshChannel


async def greet(channel: Any, name: str = "World") -> None:
    stub = demo_grpc.GreeterStub(channel)
    request = demo_pb2.HelloRequest(name=name)
    print(f"[client] sending: SayHello(name={request.name!r})", file=sys.stderr)
    response = await stub.SayHello(request)
    print(f"[client] received: {response.message}", file=sys.stderr)


async def greet_unix(path: str, name: str = "World") -> None:
    async with Channel(path=path) as channel:
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
        stdin, stdout, stderr = await conn.open_session(encoding=None)
        channel = SshChannel(stdout, stdin)
        try:
            await greet(channel, name)
        finally:
            channel.close()