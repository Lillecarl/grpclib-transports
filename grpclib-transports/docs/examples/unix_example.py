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
from greeter import common_pb2, server_grpc
from grpclib_transports import Server, connect_unix
from grpclib_transports.example.server import Greeter


async def main() -> None:
    fd, sock = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    await Path(sock).unlink()
    channel = None
    try:
        async with Server() as server:
            await server.endpoint([Greeter()]).listen_unix(sock)
            channel = connect_unix(sock)
            try:
                stub = server_grpc.GreeterStub(channel)
                response = await stub.SayHello(common_pb2.HelloRequest(name="World"))
                assert response.message == "Hello, World!"
                print(f"Greeter replied: {response.message}")
            finally:
                channel.close()
                channel = None
    finally:
        if channel is not None:
            channel.close()
        with contextlib.suppress(OSError):
            await Path(sock).unlink()


if __name__ == "__main__":
    asyncio.run(main())
