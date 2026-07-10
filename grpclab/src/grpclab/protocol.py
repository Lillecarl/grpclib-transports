import asyncio
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
from h2.settings import SettingCodes

MAX_BUF = pow(2, 20)  # 1 MiB — unified buffer size
BUF_HIGH = MAX_BUF
BUF_LOW = MAX_BUF // 2
READ_CHUNK = MAX_BUF


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


def make_server_protocol(mapping: dict[str, Handler]) -> H2Protocol:
    config = Configuration().__for_server__()
    h2_config = make_h2_config(client_side=False)
    handler = ServerHandler(mapping, ProtoCodec(), None, _DispatchServerEvents())
    return H2Protocol(handler, config, h2_config)


def init_server_protocol(protocol: H2Protocol, transport: Any) -> None:
    protocol.connection_made(transport)
    protocol.connection._connection.update_settings({
        SettingCodes.MAX_FRAME_SIZE: MAX_BUF,
    })


def build_mapping(handlers: Sequence[IServable]) -> dict[str, Handler]:
    mapping: dict[str, Handler] = {}
    for h in handlers:
        mapping.update(h.__mapping__())
    return mapping


def signal_stop(stop: asyncio.Future[None]) -> None:
    if not stop.done():
        stop.set_result(None)
