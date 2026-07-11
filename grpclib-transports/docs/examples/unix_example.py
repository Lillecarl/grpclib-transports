"""Unix domain socket transport — in-process server and client.

Run with::

    python docs/examples/unix_example.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile

from anyio import Path
from greeter import greeter_grpc, greeter_pb2
from grpclib_transports import Server, connect_unix
from grpclib_transports.example.server import Greeter


async def main() -> None:
    fd, sock = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    await Path(sock).unlink()
    server = Server([Greeter()])
    await server.start_unix(sock)
    channel = None
    try:
        channel = connect_unix(sock)
        stub = greeter_grpc.GreeterStub(channel)
        response = await stub.SayHello(greeter_pb2.HelloRequest(name="World"))
        assert response.message == "Hello, World!"
        print(f"Greeter replied: {response.message}")
    finally:
        if channel is not None:
            channel.close()
        server.close()
        await server.wait_closed()
        with contextlib.suppress(OSError):
            await Path(sock).unlink()


if __name__ == "__main__":
    asyncio.run(main())
