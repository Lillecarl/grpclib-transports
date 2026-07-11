"""Common protocol implementations shared by the runnable examples."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import greeter.greeter.server as server_grpc
import greeter.greeter.worker as worker_grpc
from greeter.greeter.common import HelloReply, HelloRequest, ManagerLookupReply, ManagerLookupRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Greeter(server_grpc.GreeterBase):
    @override
    async def say_hello(self, message: HelloRequest) -> HelloReply:
        return HelloReply(message=f"Hello, {message.name}!")

    @override
    async def upload(self, messages: AsyncIterator[HelloRequest]) -> HelloReply:
        total = 0
        async for request in messages:
            total += len(request.payload)
        return HelloReply(message=f"Uploaded {total} bytes")


class WorkerGreeter(worker_grpc.GreeterWorkerBase):
    @override
    async def say_hello(self, message: HelloRequest) -> HelloReply:
        return HelloReply(message=f"Hello, {message.name}!")

    @override
    async def upload(self, messages: AsyncIterator[HelloRequest]) -> HelloReply:
        total = 0
        async for request in messages:
            total += len(request.payload)
        return HelloReply(message=f"Uploaded {total} bytes")


class GreeterManager(worker_grpc.GreeterManagerBase):
    @override
    async def lookup(self, message: ManagerLookupRequest) -> ManagerLookupReply:
        return ManagerLookupReply(value=f"manager:{message.key}")
