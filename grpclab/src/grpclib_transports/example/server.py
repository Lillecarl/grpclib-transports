from __future__ import annotations

import asyncio
import signal
import typing

from demo import demo_grpc, demo_pb2
from grpclib.server import Server

from grpclib_transports.protocol import make_config, signal_stop


class Greeter(demo_grpc.GreeterBase):

    @typing.override
    async def SayHello(self, stream):
        request = await stream.recv_message()
        if request is None:
            return
        reply = demo_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @typing.override
    async def Upload(self, stream):
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = demo_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    server = Server([Greeter()], config=make_config())
    await server.start(path=path)

    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))
    try:
        await stop
    finally:
        server.close()
        await server.wait_closed()
