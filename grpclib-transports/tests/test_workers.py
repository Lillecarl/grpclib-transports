from __future__ import annotations

from typing import Any

from grpclib_transports import LogicalRpcPeer, Server, WorkerHost
from grpclib_transports.example.server import Greeter


async def _peer_factory(_channel: Any) -> LogicalRpcPeer:
    raise AssertionError("pool construction must not start workers")


async def test_server_for_workers_creates_worker_host() -> None:
    worker_service = Greeter()

    async with Server() as server:
        host = server.endpoint([worker_service]).for_workers()

        assert isinstance(host, WorkerHost)
        assert host.parent_services == (worker_service,)
        assert host.tuning is server.tuning


async def test_worker_host_creates_stdio_pool_with_count() -> None:
    async with Server() as server:
        host = server.endpoint([]).for_workers()

        pool = host.stdio_pool(
            ["python", "-m", "worker"],
            peer_factory=_peer_factory,
            count=3,
        )

        assert len(pool) == 0
