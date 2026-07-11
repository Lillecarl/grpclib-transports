from __future__ import annotations

import asyncio
import contextlib
import multiprocessing as mp
import os

from demo import demo_grpc, demo_pb2
from grpclib_transports.example.server import Greeter
from grpclib_transports.multiprocessing import multiprocessing_pipe_pair
from grpclib_transports.pipes import (
    PipeChannel,
    PipeTransport,
    pipe_streams_from_fds,
)
from grpclib_transports.protocol import serve_h2


async def _assert_pipe_round_trip(
    client_read_fd: int,
    client_write_fd: int,
    server_read_fd: int,
    server_write_fd: int,
) -> None:
    client_reader, client_writer, client_transport = await pipe_streams_from_fds(
        client_read_fd,
        client_write_fd,
        transport_name="client-pipe",
    )
    server_reader, _server_writer, server_transport = await pipe_streams_from_fds(
        server_read_fd,
        server_write_fd,
        transport_name="server-pipe",
    )
    server_task = asyncio.create_task(
        serve_h2([Greeter()], server_reader, server_transport),
        name="pipe-test-server",
    )
    channel = PipeChannel(
        client_reader,
        client_writer,
        transport=client_transport,
    )
    try:
        stub = demo_grpc.GreeterStub(channel)
        response = await stub.SayHello(demo_pb2.HelloRequest(name="Pipe"))
        assert response.message == "Hello, Pipe!"
    finally:
        await channel.aclose()
        server_transport.close()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task


def test_raw_pipe_transport():
    server_to_client_read, server_to_client_write = os.pipe()
    client_to_server_read, client_to_server_write = os.pipe()

    asyncio.run(
        _assert_pipe_round_trip(
            client_read_fd=server_to_client_read,
            client_write_fd=client_to_server_write,
            server_read_fd=client_to_server_read,
            server_write_fd=server_to_client_write,
        )
    )


def test_multiprocessing_pipe_pair_uses_forkserver_context():
    assert mp.get_start_method(allow_none=True) is None
    pair = multiprocessing_pipe_pair(preload=["demo"])
    assert pair.context.get_start_method() == "forkserver"
    assert mp.get_start_method(allow_none=True) is None
    try:
        asyncio.run(
            _assert_pipe_round_trip(
                client_read_fd=os.dup(pair.parent.read_connection.fileno()),
                client_write_fd=os.dup(pair.parent.write_connection.fileno()),
                server_read_fd=os.dup(pair.child.read_connection.fileno()),
                server_write_fd=os.dup(pair.child.write_connection.fileno()),
            )
        )
    finally:
        pair.close_parent_connections()
        pair.close_child_connections()
