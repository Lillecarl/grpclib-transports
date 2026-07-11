from __future__ import annotations

import asyncio

from grpclib_transports.bidi import LogicalFrame, LogicalRpcPeer, RemoteCallError


async def test_logical_rpc_peer_round_trip() -> None:
    a_to_b: asyncio.Queue[LogicalFrame | None] = asyncio.Queue()
    b_to_a: asyncio.Queue[LogicalFrame | None] = asyncio.Queue()

    async def send_a(frame: LogicalFrame) -> None:
        await a_to_b.put(frame)

    async def receive_a() -> LogicalFrame | None:
        return await b_to_a.get()

    async def send_b(frame: LogicalFrame) -> None:
        await b_to_a.put(frame)

    async def receive_b() -> LogicalFrame | None:
        return await a_to_b.get()

    async def handle_b(method: str, payload: object) -> object:
        return {"method": method, "payload": payload}

    peer_a = LogicalRpcPeer(send_frame=send_a, receive_frame=receive_a)
    peer_b = LogicalRpcPeer(
        send_frame=send_b,
        receive_frame=receive_b,
        handler=handle_b,
    )
    try:
        peer_b.start()
        response = await peer_a.call("echo", {"value": 1})
        assert response == {"method": "echo", "payload": {"value": 1}}
    finally:
        await peer_a.aclose()
        await peer_b.aclose()


async def test_logical_rpc_peer_reports_remote_errors() -> None:
    a_to_b: asyncio.Queue[LogicalFrame | None] = asyncio.Queue()
    b_to_a: asyncio.Queue[LogicalFrame | None] = asyncio.Queue()

    async def handle_b(_method: str, _payload: object) -> object:
        raise ValueError("boom")

    peer_a = LogicalRpcPeer(
        send_frame=a_to_b.put,
        receive_frame=b_to_a.get,
    )
    peer_b = LogicalRpcPeer(
        send_frame=b_to_a.put,
        receive_frame=a_to_b.get,
        handler=handle_b,
    )
    try:
        peer_b.start()
        try:
            await peer_a.call("fail")
        except RemoteCallError as e:
            assert str(e) == "boom"
        else:
            raise AssertionError("expected RemoteCallError")
    finally:
        await peer_a.aclose()
        await peer_b.aclose()
