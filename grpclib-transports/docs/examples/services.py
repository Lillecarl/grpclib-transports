"""Common protocol implementations shared by the runnable examples."""

from __future__ import annotations

from typing import Any, override

from greeter import common_pb2, server_grpc, worker_grpc


class Greeter(server_grpc.GreeterBase):
    @override
    async def SayHello(self, stream: Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        reply = common_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @override
    async def Upload(self, stream: Any) -> None:
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = common_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


class WorkerGreeter(worker_grpc.GreeterWorkerBase):
    @override
    async def SayHello(self, stream: Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        reply = common_pb2.HelloReply(message=f"Hello, {request.name}!")
        await stream.send_message(reply)

    @override
    async def Upload(self, stream: Any) -> None:
        total = 0
        while True:
            request = await stream.recv_message()
            if request is None:
                break
            total += len(request.payload)
        reply = common_pb2.HelloReply(message=f"Uploaded {total} bytes")
        await stream.send_message(reply)


class GreeterManager(worker_grpc.GreeterManagerBase):
    @override
    async def Lookup(self, stream: Any) -> None:
        request = await stream.recv_message()
        if request is None:
            return
        await stream.send_message(common_pb2.ManagerLookupReply(value=f"manager:{request.key}"))
