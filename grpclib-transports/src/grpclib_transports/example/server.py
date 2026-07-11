from __future__ import annotations

import asyncio
import signal
import typing

from greeter import common_pb2, server_grpc, worker_grpc

from grpclib_transports.protocol import signal_stop
from grpclib_transports.server import Server


class Greeter(server_grpc.GreeterBase):
    @typing.override
    async def SayHello(self, stream: typing.Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        reply = common_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @typing.override
    async def Upload(self, stream: typing.Any) -> None:
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = common_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


class WorkerGreeter(worker_grpc.GreeterWorkerBase):
    @typing.override
    async def SayHello(self, stream: typing.Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        reply = common_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @typing.override
    async def Upload(self, stream: typing.Any) -> None:
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = common_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))

    async with Server() as server:
        await server.endpoint([Greeter()]).listen_unix(path)
        await stop
