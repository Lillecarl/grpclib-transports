from __future__ import annotations

import asyncio
import signal
import typing

from greeter import greeter_grpc, greeter_pb2

from grpclib_transports.protocol import signal_stop
from grpclib_transports.server import Server


class Greeter(greeter_grpc.GreeterBase):
    @typing.override
    async def SayHello(self, stream: typing.Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        reply = greeter_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @typing.override
    async def Upload(self, stream: typing.Any) -> None:
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = greeter_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    server = Server([Greeter()])
    await server.start_unix(path)

    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))
    try:
        await stop
    finally:
        server.close()
        await server.wait_closed()
