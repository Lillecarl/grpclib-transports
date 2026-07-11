"""Multiprocessing pipe-pair helpers: forkserver contexts and dup'd FDs."""

from __future__ import annotations

import multiprocessing as mp
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from grpclib_transports.pipes import PipeChannel, pipe_streams_from_fds
from grpclib_transports.protocol import DEFAULT_TUNING, TransportTuning

if TYPE_CHECKING:
    from collections.abc import Sequence


def get_forkserver_context(
    *,
    preload: Sequence[str] = (),
) -> Any:
    """Return a ``multiprocessing`` forkserver context, optionally preloading modules."""
    context = mp.get_context("forkserver")
    if preload:
        context.set_forkserver_preload(list(preload))
    return context


@dataclass(frozen=True)
class MultiprocessingPipeEndpoint:
    """One end of a multiprocessing pipe pair.

    Call :meth:`open_channel` to create a :class:`~grpclib_transports.pipes.PipeChannel`
    backed by the pipe file descriptors.
    """

    read_connection: Any
    write_connection: Any
    transport_name: str = "multiprocessing"

    async def open_channel(
        self,
        *,
        tuning: TransportTuning = DEFAULT_TUNING,
    ) -> PipeChannel:
        read_fd = os.dup(self.read_connection.fileno())
        write_fd = os.dup(self.write_connection.fileno())
        reader, writer, transport = await pipe_streams_from_fds(
            read_fd,
            write_fd,
            transport_name=self.transport_name,
            tuning=tuning,
        )
        return PipeChannel(
            reader,
            writer,
            transport=transport,
            tuning=tuning,
        )

    def close_connections(self) -> None:
        self.read_connection.close()
        self.write_connection.close()


@dataclass(frozen=True)
class MultiprocessingPipePair:
    """A pair of :class:`MultiprocessingPipeEndpoint` — one for parent, one for child."""

    parent: MultiprocessingPipeEndpoint
    child: MultiprocessingPipeEndpoint
    context: Any

    def close_parent_connections(self) -> None:
        self.parent.close_connections()

    def close_child_connections(self) -> None:
        self.child.close_connections()


def multiprocessing_pipe_pair(
    *,
    context: Any | None = None,
    preload: Sequence[str] = (),
) -> MultiprocessingPipePair:
    """Create a :class:`MultiprocessingPipePair` for parent-child communication.

    If *context* is not given, calls :func:`get_forkserver_context` with *preload*.
    """
    ctx = context or get_forkserver_context(preload=preload)
    if context is not None and preload:
        ctx.set_forkserver_preload(list(preload))
    parent_read, child_write = ctx.Pipe(duplex=False)
    child_read, parent_write = ctx.Pipe(duplex=False)
    return MultiprocessingPipePair(
        parent=MultiprocessingPipeEndpoint(
            read_connection=parent_read,
            write_connection=parent_write,
        ),
        child=MultiprocessingPipeEndpoint(
            read_connection=child_read,
            write_connection=child_write,
        ),
        context=ctx,
    )
