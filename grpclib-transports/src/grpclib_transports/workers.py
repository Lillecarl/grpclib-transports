"""Stdio worker pools: managed subprocess groups bridged by logical peers."""

from __future__ import annotations

import contextlib
import itertools
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from grpclib_transports.bidi import LogicalRpcPeer
from grpclib_transports.protocol import DEFAULT_TUNING, TransportTuning
from grpclib_transports.stdio import StdioChannel, stdio_worker

PeerT = TypeVar("PeerT", bound=LogicalRpcPeer)
PeerFactory = Callable[[StdioChannel], Awaitable[PeerT]]


@dataclass(frozen=True)
class RegisteredPeer(Generic[PeerT]):
    """A :class:`LogicalRpcPeer` registered with an ID and optional metadata.

    Delegates :meth:`call` and :meth:`event` to the wrapped peer.
    """

    id: str
    peer: PeerT
    metadata: Mapping[str, Any] = field(default_factory=dict)

    async def call(
        self,
        method: str,
        payload: Any = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        return await self.peer.call(method, payload, timeout=timeout)

    async def event(self, method: str, payload: Any = None) -> None:
        await self.peer.event(method, payload)


class PeerRegistry(Generic[PeerT]):
    """A thread-unsafe registry of :class:`RegisteredPeer` instances.

    Supports :func:`len`, iteration, and snapshot via :meth:`snapshot`.
    Broadcast calls to all registered peers with :meth:`call_all`.
    """

    def __init__(self) -> None:
        self._next_id = itertools.count(1)
        self._peers: dict[str, RegisteredPeer[PeerT]] = {}

    def __len__(self) -> int:
        return len(self._peers)

    def __iter__(self) -> Iterator[RegisteredPeer[PeerT]]:
        return iter(self.snapshot())

    def register(
        self,
        peer: PeerT,
        *,
        peer_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RegisteredPeer[PeerT]:
        resolved_id = peer_id or f"peer-{next(self._next_id)}"
        if resolved_id in self._peers:
            raise ValueError(f"peer {resolved_id!r} is already registered")
        registered = RegisteredPeer(
            id=resolved_id,
            peer=peer,
            metadata=metadata or {},
        )
        self._peers[resolved_id] = registered
        return registered

    def unregister(self, peer_id: str) -> RegisteredPeer[PeerT] | None:
        return self._peers.pop(peer_id, None)

    def get(self, peer_id: str) -> RegisteredPeer[PeerT] | None:
        return self._peers.get(peer_id)

    def snapshot(self) -> tuple[RegisteredPeer[PeerT], ...]:
        return tuple(self._peers.values())

    async def call_all(
        self,
        method: str,
        payload: Any = None,
        *,
        timeout: float | None = None,
    ) -> list[Any]:
        return [await peer.call(method, payload, timeout=timeout) for peer in self.snapshot()]

    async def aclose(self) -> None:
        for registered in self.snapshot():
            await registered.peer.aclose()
            self.unregister(registered.id)


class StdioPeerPool(Generic[PeerT]):
    """A pool of *size* subprocess workers, each bridged by a :class:`LogicalRpcPeer`.

    Use as an async context manager.  On enter, spawns *size* child processes
    via :func:`~grpclib_transports.stdio.stdio_worker`, creates peers with
    *peer_factory*, and registers them in :attr:`registry`.  On exit, closes
    all peers and terminates all subprocesses.
    """

    def __init__(
        self,
        argv: Sequence[str | Path],
        *,
        peer_factory: PeerFactory[PeerT],
        size: int = 1,
        tuning: TransportTuning = DEFAULT_TUNING,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        stderr: Any = None,
    ) -> None:
        if size <= 0:
            raise ValueError("size must be positive")
        self._argv = argv
        self._peer_factory = peer_factory
        self._size = size
        self._tuning = tuning
        self._cwd = cwd
        self._env = env
        self._stderr = stderr
        self._stack = contextlib.AsyncExitStack()
        self.registry: PeerRegistry[PeerT] = PeerRegistry()

    def __len__(self) -> int:
        return len(self.registry)

    def __iter__(self) -> Iterator[RegisteredPeer[PeerT]]:
        return iter(self.registry)

    async def __aenter__(self) -> StdioPeerPool[PeerT]:
        for index in range(self._size):
            channel = await self._stack.enter_async_context(
                stdio_worker(
                    self._argv,
                    tuning=self._tuning,
                    cwd=self._cwd,
                    env=self._env,
                    stderr=self._stderr,
                )
            )
            peer = await self._peer_factory(channel)
            peer.start()
            self.registry.register(
                peer,
                peer_id=f"stdio-{index + 1}",
                metadata={"transport": "stdio", "index": index},
            )
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.registry.aclose()
        await self._stack.aclose()
