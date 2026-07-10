from __future__ import annotations

import asyncio
import signal
from typing import Any

from grpclib import client
from grpclib.protocol import H2Protocol

from grpclab.protocol import (
    DEFAULT_TUNING,
    BaseCustomTransport,
    TransportTuning,
    build_mapping,
    init_server_protocol,
    make_config,
    make_server_protocol,
    pump,
    signal_stop,
)


class SshTransport(BaseCustomTransport):

    def __init__(
        self,
        reader: Any,
        writer: Any,
        *,
        tuning: TransportTuning = DEFAULT_TUNING,
    ):
        super().__init__()
        self._reader = reader
        self._writer = writer
        self._tuning = tuning

        chan = writer._chan
        chan.set_write_buffer_limits(
            high=tuning.write_high_water,
            low=tuning.write_low_water,
        )
        self._chan = chan

        self._session = writer._session
        self._orig_pause_writing = self._session.pause_writing
        self._orig_resume_writing = self._session.resume_writing
        self._session.pause_writing = self._on_pause_writing
        self._session.resume_writing = self._on_resume_writing

    def _restore_session_callbacks(self) -> None:
        if self._orig_pause_writing is not None:
            self._session.pause_writing = self._orig_pause_writing
            self._orig_pause_writing = None
        if self._orig_resume_writing is not None:
            self._session.resume_writing = self._orig_resume_writing
            self._orig_resume_writing = None

    def _on_pause_writing(self) -> None:
        if self._orig_pause_writing is not None:
            self._orig_pause_writing()
        if self._protocol is not None:
            self._protocol.pause_writing()

    def _on_resume_writing(self) -> None:
        if self._orig_resume_writing is not None:
            self._orig_resume_writing()
        if self._protocol is not None:
            self._protocol.resume_writing()

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self._writer.write(data)

    def get_write_buffer_size(self) -> int:
        return self._chan.get_write_buffer_size()

    def close(self) -> None:
        self._closing = True
        self._restore_session_callbacks()
        self._writer.close()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name in ("username", "session", "channel"):
            return self._writer.get_extra_info(name)
        return self._chan.get_extra_info(name, default)

    def abort(self) -> None:
        self._closing = True
        self._restore_session_callbacks()
        self._writer.abort()

    def can_write_eof(self) -> bool:
        return self._chan.can_write_eof()

    def write_eof(self) -> None:
        self._writer.write_eof()

    def set_write_buffer_limits(
        self, high: int | None = None, low: int | None = None
    ) -> None:
        self._chan.set_write_buffer_limits(high=high, low=low)


async def serve_ssh(
    handlers: list,
    host: str = "127.0.0.1",
    port: int = 8022,
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
) -> None:
    import asyncssh

    key = asyncssh.generate_private_key("ssh-ed25519")
    mapping = build_mapping(handlers)

    class _DemoSSHServer(asyncssh.SSHServer):
        def password_auth_supported(self):
            return True
        def validate_password(self, username: str, password: str) -> bool:
            return True

    async def session_handler(stdin, stdout, _stderr) -> None:
        transport = SshTransport(stdin, stdout, tuning=tuning)
        protocol = make_server_protocol(mapping, tuning=tuning)
        init_server_protocol(protocol, transport, tuning=tuning)

        await pump(protocol, stdin, tuning=tuning)

    acceptor = await asyncssh.create_server(
        _DemoSSHServer,
        host,
        port,
        server_host_keys=[key],
        session_factory=session_handler,
        encoding=None,
        line_editor=False,
    )

    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_stop(stop))
    try:
        await stop
    finally:
        acceptor.close()
        await acceptor.wait_closed()


class SshChannel(client.Channel):

    def __init__(
        self,
        reader: Any,
        writer: Any,
        *,
        tuning: TransportTuning = DEFAULT_TUNING,
        **kwargs: Any,
    ):
        kwargs.setdefault("config", make_config(tuning))
        super().__init__(host="ssh", port=0, **kwargs)
        self._ssh_reader = reader
        self._ssh_writer = writer
        self._tuning = tuning
        self._pump_task: asyncio.Task[None] | None = None
        self._ssh_transport: SshTransport | None = None

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        transport = SshTransport(
            self._ssh_reader,
            self._ssh_writer,
            tuning=self._tuning,
        )
        self._ssh_transport = transport
        init_server_protocol(protocol, transport, tuning=self._tuning)
        self._pump_task = asyncio.create_task(
            pump(protocol, self._ssh_reader, tuning=self._tuning),
            name="ssh-pump",
        )
        return protocol

    def close(self) -> None:
        super().close()
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
        if self._ssh_transport is not None:
            self._ssh_transport.close()
        self._ssh_writer.close()
