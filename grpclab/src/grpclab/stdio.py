from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Any

from grpclib import client
from grpclib.protocol import H2Protocol

from grpclab.protocol import (
    BUF_HIGH,
    BUF_LOW,
    BaseCustomTransport,
    build_mapping,
    init_server_protocol,
    make_config,
    make_server_protocol,
    pump,
)


class StdioTransport(BaseCustomTransport):

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__()
        self._reader = reader
        self._writer = writer

        pipe_transport = writer.transport
        pipe_transport.set_write_buffer_limits(high=BUF_HIGH, low=BUF_LOW)

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self._writer.write(data)

    def get_write_buffer_size(self) -> int:
        return self._writer.transport.get_write_buffer_size()

    def close(self) -> None:
        self._closing = True
        self._writer.close()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        return self._writer.get_extra_info(name, default)

    def abort(self) -> None:
        # Pipes have no hard abort — close() is the best we can do.
        self._closing = True
        self._writer.close()

    def can_write_eof(self) -> bool:
        return False

    def write_eof(self) -> None:
        pass


async def _stdio_streams() -> tuple[asyncio.StreamReader, asyncio.StreamWriter, StdioTransport]:
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin.buffer,
    )

    transport_ref: list[StdioTransport] = []

    class _Bridge(asyncio.Protocol):
        def pause_writing(self) -> None:
            if transport_ref and transport_ref[0]._protocol:
                transport_ref[0]._protocol.pause_writing()
        def resume_writing(self) -> None:
            if transport_ref and transport_ref[0]._protocol:
                transport_ref[0]._protocol.resume_writing()

    t, proto = await loop.connect_write_pipe(
        lambda: _Bridge(),
        sys.stdout.buffer,
    )
    writer = asyncio.StreamWriter(t, proto, reader, loop)

    transport = StdioTransport(reader, writer)
    transport_ref.append(transport)

    return reader, writer, transport


async def serve_stdio(handlers: list) -> None:
    mapping = build_mapping(handlers)

    reader, _writer, transport = await _stdio_streams()

    protocol = make_server_protocol(mapping)
    init_server_protocol(protocol, transport)

    with contextlib.redirect_stdout(sys.stderr):
        await pump(protocol, reader)


class StdioChannel(client.Channel):

    def __init__(
        self,
        reader: Any,
        writer: Any,
        *,
        transport: StdioTransport | None = None,
        **kwargs: Any,
    ):
        kwargs.setdefault("config", make_config())
        super().__init__(host="stdio", port=0, **kwargs)
        self._stdio_reader = reader
        self._stdio_writer = writer
        self._stdio_transport = transport
        self._pump_task: asyncio.Task[None] | None = None

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        transport = self._stdio_transport or StdioTransport(
            self._stdio_reader, self._stdio_writer
        )
        self._stdio_transport = transport
        init_server_protocol(protocol, transport)
        self._pump_task = asyncio.create_task(
            pump(protocol, self._stdio_reader), name="stdio-pump"
        )
        return protocol

    def close(self) -> None:
        super().close()
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
        if self._stdio_transport is not None:
            self._stdio_transport.close()
