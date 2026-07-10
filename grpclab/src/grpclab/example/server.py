from __future__ import annotations

import asyncio
import signal
import typing

from demo import demo_grpc, demo_pb2
from grpclib.server import Server

from grpclab.protocol import signal_stop


class Greeter(demo_grpc.GreeterBase):

    @typing.override
    async def SayHello(self, stream):
        request = await stream.recv_message()
        reply = demo_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    server = Server([Greeter()])
    await server.start(path=path)

    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))
    try:
        await stop
    finally:
        server.close()
        await server.wait_closed()
