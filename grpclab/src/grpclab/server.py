import asyncio
import signal
import sys
from grpclib.server import Server
from demo import demo_pb2, demo_grpc


class Greeter(demo_grpc.GreeterBase):

    async def SayHello(self, stream):
        request = await stream.recv_message()
        print(f"[server] received: SayHello(name={request.name!r})", file=sys.stderr)
        reply = demo_pb2.HelloReply(message=f"Hello, {request.name}!")
        print(f"[server] sending: {reply.message}", file=sys.stderr)
        await stream.send_message(reply)


async def serve(path: str) -> None:
    loop = asyncio.get_running_loop()
    server = Server([Greeter()])
    await server.start(path=path)
    print(f"[server] listening on {path}")

    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: stop.set_result(None))
    try:
        await stop
    finally:
        server.close()
        await server.wait_closed()
