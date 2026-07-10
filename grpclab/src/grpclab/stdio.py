import asyncio
import contextlib
import sys
from typing import Optional

from h2.config import H2Configuration
from grpclib.config import Configuration
from grpclib.protocol import H2Protocol
from grpclib import client
from grpclib.server import Handler as ServerHandler
from grpclib.events import _DispatchServerEvents
from grpclib.encoding.proto import ProtoCodec


class StreamReaderWriterTransport(asyncio.Transport):

    def __init__(self, reader, writer):
        super().__init__()
        self._reader = reader
        self._writer = writer
        self._protocol: Optional[asyncio.Protocol] = None
        self._closing = False

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    def close(self) -> None:
        self._closing = True
        self._writer.close()

    def is_closing(self) -> bool:
        return self._closing

    def get_extra_info(self, name, default=None):
        return self._writer.get_extra_info(name, default)

    def get_protocol(self):
        return self._protocol

    def set_protocol(self, protocol):
        self._protocol = protocol

    def abort(self):
        self._closing = True
        self._writer.close()

    def can_write_eof(self):
        return False

    def write_eof(self):
        pass

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass


class StdioTransport(asyncio.Transport):

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__()
        self._reader = reader
        self._writer = writer
        self._protocol: Optional[asyncio.Protocol] = None
        self._closing = False

        pipe_transport = writer.transport
        pipe_transport.set_write_buffer_limits(high=65536, low=32768)

    def write(self, data: bytes) -> None:
        self._writer.write(data)

    def get_write_buffer_size(self) -> int:
        return self._writer.transport.get_write_buffer_size()

    def close(self) -> None:
        self._closing = True
        self._writer.close()

    def is_closing(self) -> bool:
        return self._closing

    def get_extra_info(self, name, default=None):
        return self._writer.get_extra_info(name, default)

    def get_protocol(self):
        return self._protocol

    def set_protocol(self, protocol):
        self._protocol = protocol

    def abort(self):
        self._closing = True
        self._writer.close()

    def can_write_eof(self):
        return False

    def write_eof(self):
        pass

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass


async def _pump(protocol: H2Protocol, reader) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            protocol.data_received(data)
    except (ConnectionError, EOFError, OSError):
        pass
    finally:
        protocol.connection_lost(None)


async def _stdio_streams():
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin.buffer,
    )

    transport_ref: list[StdioTransport] = []

    class _Bridge(asyncio.Protocol):
        def pause_writing(self):
            if transport_ref and transport_ref[0]._protocol:
                transport_ref[0]._protocol.pause_writing()
        def resume_writing(self):
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
    mapping = {}
    for h in handlers:
        mapping.update(h.__mapping__())

    config = Configuration().__for_server__()
    h2_config = H2Configuration(
        client_side=False,
        header_encoding="ascii",
        validate_inbound_headers=False,
        validate_outbound_headers=False,
        normalize_inbound_headers=False,
        normalize_outbound_headers=False,
    )

    reader, writer, transport = await _stdio_streams()

    handler = ServerHandler(
        mapping,
        ProtoCodec(),
        None,
        _DispatchServerEvents(),
    )
    protocol = H2Protocol(handler, config, h2_config)
    protocol.connection_made(transport)
    transport._protocol = protocol

    print("[server] running on stdin/stdout", file=sys.stderr)
    with contextlib.redirect_stdout(sys.stderr):
        await _pump(protocol, reader)


class StdioChannel(client.Channel):

    def __init__(
        self,
        reader,
        writer,
        *,
        transport: Optional[StdioTransport] = None,
        **kwargs,
    ):
        super().__init__(host="stdio", port=0, **kwargs)
        self._stdio_reader = reader
        self._stdio_writer = writer
        self._stdio_transport = transport

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        if self._stdio_transport is not None:
            transport = self._stdio_transport
        else:
            transport = StreamReaderWriterTransport(self._stdio_reader, self._stdio_writer)
        protocol.connection_made(transport)
        asyncio.create_task(_pump(protocol, self._stdio_reader))
        return protocol
