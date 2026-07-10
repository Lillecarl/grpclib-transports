from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from typing import Any

from grpclib._typing import IServable
from grpclib.config import Configuration
from grpclib.const import Handler
from grpclib.encoding.proto import ProtoCodec
from grpclib.events import _DispatchServerEvents
from grpclib.protocol import H2Protocol
from grpclib.server import Handler as ServerHandler
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.errors import ErrorCodes
from h2.exceptions import StreamClosedError, StreamIDTooLowError
from h2.settings import SettingCodes
from hyperframe.frame import RstStreamFrame


def _env_size(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer byte count") from e
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _receive_frame(self: H2Connection, frame: Any) -> list[Any]:
    events: list
    try:
        frames, events = self._frame_dispatch_table[frame.__class__](frame)
    except StreamClosedError as e:
        if self._stream_is_closed_by_reset(e.stream_id):
            f = RstStreamFrame(e.stream_id)
            f.error_code = e.error_code
            self._prepare_for_sending([f])
            events = e._events
        else:
            raise
    except StreamIDTooLowError as e:
        if self._stream_is_closed_by_reset(e.stream_id):
            f = RstStreamFrame(e.stream_id)
            f.error_code = ErrorCodes.STREAM_CLOSED
            self._prepare_for_sending([f])
            events = []
        elif self._stream_is_closed_by_end(e.stream_id):
            raise StreamClosedError(e.stream_id) from e
        else:
            raise
    else:
        self._prepare_for_sending(frames)
    return events


H2Connection._receive_frame = _receive_frame

MAX_FRAME_SIZE = 2**24 - 1

MAX_BUF = _env_size("GRPCLAB_BUFFER_SIZE", 8 * 1024 * 1024)
BUF_HIGH = MAX_BUF
BUF_LOW = MAX_BUF // 2
READ_CHUNK = MAX_BUF
HTTP2_STREAM_WINDOW_SIZE = _env_size(
    "GRPCLAB_HTTP2_STREAM_WINDOW_SIZE",
    max(16 * 1024 * 1024, MAX_BUF * 2),
)
HTTP2_CONNECTION_WINDOW_SIZE = _env_size(
    "GRPCLAB_HTTP2_CONNECTION_WINDOW_SIZE",
    max(64 * 1024 * 1024, HTTP2_STREAM_WINDOW_SIZE * 4),
)
HTTP2_MAX_FRAME_SIZE = min(MAX_BUF, MAX_FRAME_SIZE)


class BaseCustomTransport(asyncio.Transport):
    """Base class for custom asyncio transports that wrap a reader/writer pair.

    Concrete transports (StdioTransport, SshTransport) override:
    - ``write()``         — forward data to the underlying writer
    - ``get_extra_info()`` — delegate to the appropriate underlying object
    - ``get_write_buffer_size()`` — introspect the write buffer (for flow control)
    - ``abort()``         — hard reset (transport-specific)
    - ``can_write_eof()`` / ``write_eof()`` — EOF support (transport-specific)

    Flow-control bridging (pause_writing/resume_writing forwarding to the
    H2Protocol) is handled by each concrete transport's own mechanism.
    """

    def __init__(self) -> None:
        super().__init__()
        self._protocol: asyncio.BaseProtocol | None = None
        self._closing = False

    def is_closing(self) -> bool:
        return self._closing

    def get_protocol(self) -> asyncio.BaseProtocol:
        protocol = self._protocol
        if protocol is None:
            raise RuntimeError("protocol has not been set yet")
        return protocol

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        self._protocol = protocol

    def pause_reading(self) -> None:
        pass

    def resume_reading(self) -> None:
        pass


async def pump(protocol: H2Protocol, reader: Any) -> None:
    exc: BaseException | None = None
    try:
        while True:
            data = await reader.read(READ_CHUNK)
            if not data:
                break
            protocol.data_received(data)
    except (ConnectionError, OSError) as e:
        exc = e
    finally:
        protocol.connection_lost(exc)


def make_h2_config(*, client_side: bool) -> H2Configuration:
    return H2Configuration(
        client_side=client_side,
        header_encoding="ascii",
        validate_inbound_headers=False,
        validate_outbound_headers=False,
        normalize_inbound_headers=False,
        normalize_outbound_headers=False,
    )


def make_config() -> Configuration:
    return Configuration(
        http2_connection_window_size=HTTP2_CONNECTION_WINDOW_SIZE,
        http2_stream_window_size=HTTP2_STREAM_WINDOW_SIZE,
    )


def make_server_protocol(mapping: dict[str, Handler]) -> H2Protocol:
    config = make_config().__for_server__()
    h2_config = make_h2_config(client_side=False)
    handler = ServerHandler(mapping, ProtoCodec(), None, _DispatchServerEvents())
    return H2Protocol(handler, config, h2_config)


def init_server_protocol(protocol: H2Protocol, transport: Any) -> None:
    transport.set_protocol(protocol)
    protocol.connection_made(transport)
    protocol.connection._connection.update_settings({
        SettingCodes.MAX_FRAME_SIZE: HTTP2_MAX_FRAME_SIZE,
    })
    protocol.connection.flush()


def build_mapping(handlers: Sequence[IServable]) -> dict[str, Handler]:
    mapping: dict[str, Handler] = {}
    for h in handlers:
        mapping.update(h.__mapping__())
    return mapping


def signal_stop(stop: asyncio.Future[None]) -> None:
    if not stop.done():
        stop.set_result(None)
