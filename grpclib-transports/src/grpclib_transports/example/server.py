from __future__ import annotations

import asyncio
import signal
import typing

import greeter2.greeter.server as server_grpc
import greeter2.greeter.worker as worker_grpc
from greeter2.greeter.common import HelloReply, HelloRequest
from grpclib_transports.protocol import signal_stop
from grpclib_transports.server import Server

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Greeter(server_grpc.GreeterBase):
    @typing.override
    async def say_hello(self, message: HelloRequest) -> HelloReply:
        return HelloReply(message=f"Hello, {message.name}!")

    @typing.override
    async def upload(self, messages: AsyncIterator[HelloRequest]) -> HelloReply:
        total = 0
        async for request in messages:
            total += len(request.payload)
        return HelloReply(message=f"Uploaded {total} bytes")


class WorkerGreeter(worker_grpc.GreeterWorkerBase):
    @typing.override
    async def say_hello(self, message: HelloRequest) -> HelloReply:
        return HelloReply(message=f"Hello, {message.name}!")

    @typing.override
    async def upload(self, messages: AsyncIterator[HelloRequest]) -> HelloReply:
        total = 0
        async for request in messages:
            total += len(request.payload)
        return HelloReply(message=f"Uploaded {total} bytes")


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))

    async with Server() as server:
        await server.endpoint([Greeter()]).listen_unix(path)
        await stop
