from typing import Any, Mapping, Sequence

from h2.config import H2Configuration
from grpclib.config import Configuration
from grpclib.const import Handler
from grpclib.encoding.proto import ProtoCodec
from grpclib.events import _DispatchServerEvents
from grpclib.protocol import H2Protocol
from grpclib.server import Handler as ServerHandler
from grpclib._typing import IServable


BUF_HIGH = pow(2, 19)  # 512 KiB — high watermark for write buffering
BUF_LOW = pow(2, 18)   # 256 KiB — low watermark for write buffering
READ_CHUNK = pow(2, 19)  # 512 KiB — read chunk size for pump()


async def pump(protocol: H2Protocol, reader: Any) -> None:
    try:
        while True:
            data = await reader.read(READ_CHUNK)
            if not data:
                break
            protocol.data_received(data)
    except (ConnectionError, OSError):
        pass
    finally:
        protocol.connection_lost(None)


def make_h2_config(*, client_side: bool) -> H2Configuration:
    return H2Configuration(
        client_side=client_side,
        header_encoding="ascii",
        validate_inbound_headers=False,
        validate_outbound_headers=False,
        normalize_inbound_headers=False,
        normalize_outbound_headers=False,
    )


def make_server_protocol(mapping: Mapping[str, Handler]) -> H2Protocol:
    config = Configuration().__for_server__()
    h2_config = make_h2_config(client_side=False)
    handler = ServerHandler(mapping, ProtoCodec(), None, _DispatchServerEvents())
    return H2Protocol(handler, config, h2_config)


def build_mapping(handlers: Sequence[IServable]) -> dict[str, Handler]:
    mapping: dict[str, Handler] = {}
    for h in handlers:
        mapping.update(h.__mapping__())
    return mapping