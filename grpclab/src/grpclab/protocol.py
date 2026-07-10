from __future__ import annotations

import asyncio
import inspect
import os
from collections.abc import Sequence
from dataclasses import dataclass
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


_H2_FAST_RECEIVE_PATCH_INSTALLED = False


def _receive_frame_without_trace_repr(
    self: H2Connection,
    frame: Any,
) -> list[Any]:
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


def install_h2_fast_receive_patch() -> None:
    """Avoid h2's trace logging frame repr cost without changing frame handling."""
    global _H2_FAST_RECEIVE_PATCH_INSTALLED

    if _H2_FAST_RECEIVE_PATCH_INSTALLED:
        return

    params = tuple(inspect.signature(H2Connection._receive_frame).parameters)
    if params != ("self", "frame"):
        raise RuntimeError(
            "Unsupported h2 H2Connection._receive_frame signature: "
            f"{params!r}"
        )
    H2Connection._receive_frame = _receive_frame_without_trace_repr
    _H2_FAST_RECEIVE_PATCH_INSTALLED = True


install_h2_fast_receive_patch()

MAX_FRAME_SIZE = 2**24 - 1


@dataclass(frozen=True)
class TransportTuning:
    buffer_size: int
    read_chunk_size: int
    write_high_water: int
    write_low_water: int
    http2_stream_window_size: int
    http2_connection_window_size: int
    http2_max_frame_size: int

    @classmethod
    def from_env(cls) -> TransportTuning:
        buffer_size = _env_size("GRPCLAB_BUFFER_SIZE", 8 * 1024 * 1024)
        stream_window_size = _env_size(
            "GRPCLAB_HTTP2_STREAM_WINDOW_SIZE",
            max(16 * 1024 * 1024, buffer_size * 2),
        )
        connection_window_size = _env_size(
            "GRPCLAB_HTTP2_CONNECTION_WINDOW_SIZE",
            max(64 * 1024 * 1024, stream_window_size * 4),
        )
        return cls(
            buffer_size=buffer_size,
            read_chunk_size=buffer_size,
            write_high_water=buffer_size,
            write_low_water=buffer_size // 2,
            http2_stream_window_size=stream_window_size,
            http2_connection_window_size=connection_window_size,
            http2_max_frame_size=min(buffer_size, MAX_FRAME_SIZE),
        )


DEFAULT_TUNING = TransportTuning.from_env()


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


async def pump(
    protocol: H2Protocol,
    reader: Any,
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
) -> None:
    exc: BaseException | None = None
    try:
        while True:
            data = await reader.read(tuning.read_chunk_size)
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


def make_config(tuning: TransportTuning = DEFAULT_TUNING) -> Configuration:
    return Configuration(
        http2_connection_window_size=tuning.http2_connection_window_size,
        http2_stream_window_size=tuning.http2_stream_window_size,
    )


def make_server_protocol(
    mapping: dict[str, Handler],
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
) -> H2Protocol:
    config = make_config(tuning).__for_server__()
    h2_config = make_h2_config(client_side=False)
    handler = ServerHandler(mapping, ProtoCodec(), None, _DispatchServerEvents())
    return H2Protocol(handler, config, h2_config)


def init_h2_transport(
    protocol: H2Protocol,
    transport: Any,
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
) -> None:
    transport.set_protocol(protocol)
    protocol.connection_made(transport)
    protocol.connection._connection.update_settings({
        SettingCodes.MAX_FRAME_SIZE: tuning.http2_max_frame_size,
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
