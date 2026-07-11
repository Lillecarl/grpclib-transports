from __future__ import annotations

import socket
from collections.abc import Collection
from pathlib import Path
from ssl import SSLContext
from typing import Any

from grpclib._typing import IServable
from grpclib.encoding.base import CodecBase, StatusDetailsCodecBase
from grpclib.server import Server as GrpclibServer

from grpclib_transports.protocol import DEFAULT_TUNING, TransportTuning, make_config


class Server:
    def __init__(
        self,
        handlers: Collection[IServable],
        *,
        tuning: TransportTuning = DEFAULT_TUNING,
        codec: CodecBase | None = None,
        status_details_codec: StatusDetailsCodecBase | None = None,
    ) -> None:
        self.tuning = tuning
        self._server = GrpclibServer(
            handlers,
            codec=codec,
            status_details_codec=status_details_codec,
            config=make_config(tuning),
        )

    @property
    def raw_server(self) -> GrpclibServer:
        return self._server

    async def start(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        path: str | Path | None = None,
        family: socket.AddressFamily = socket.AF_UNSPEC,
        flags: socket.AddressInfo = socket.AI_PASSIVE,
        sock: socket.socket | None = None,
        backlog: int = 100,
        ssl: SSLContext | None = None,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
    ) -> None:
        await self._server.start(
            host=host,
            port=port,
            path=str(path) if path is not None else None,
            family=family,
            flags=flags,
            sock=sock,
            backlog=backlog,
            ssl=ssl,
            reuse_address=reuse_address,
            reuse_port=reuse_port,
        )

    async def start_unix(
        self,
        path: str | Path,
        *,
        backlog: int = 100,
    ) -> None:
        await self.start(path=path, backlog=backlog)

    async def start_tcp(
        self,
        host: str,
        port: int,
        *,
        family: socket.AddressFamily = socket.AF_UNSPEC,
        flags: socket.AddressInfo = socket.AI_PASSIVE,
        backlog: int = 100,
        ssl: SSLContext | None = None,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
    ) -> None:
        await self.start(
            host=host,
            port=port,
            family=family,
            flags=flags,
            backlog=backlog,
            ssl=ssl,
            reuse_address=reuse_address,
            reuse_port=reuse_port,
        )

    def close(self) -> None:
        self._server.close()

    async def wait_closed(self) -> None:
        await self._server.wait_closed()

    async def __aenter__(self) -> Server:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self.close()
        await self.wait_closed()
