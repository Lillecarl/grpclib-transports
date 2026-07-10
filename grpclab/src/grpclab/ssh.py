import asyncio
import signal
import sys
from typing import Any, Optional

from grpclib.protocol import H2Protocol
from grpclib import client

from grpclab.protocol import (
    BaseCustomTransport,
    pump,
    BUF_HIGH,
    BUF_LOW,
    make_server_protocol,
    build_mapping,
    signal_stop,
)


class SshTransport(BaseCustomTransport):

    def __init__(self, reader: Any, writer: Any):
        super().__init__()
        self._reader = reader
        self._writer = writer

        chan = writer._chan
        chan.set_write_buffer_limits(high=BUF_HIGH, low=BUF_LOW)
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
        self._orig_pause_writing()
        if self._protocol is not None:
            self._protocol.pause_writing()

    def _on_resume_writing(self) -> None:
        self._orig_resume_writing()
        if self._protocol is not None:
            self._protocol.resume_writing()

    def write(self, data: bytes) -> None:
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
        self, high: Optional[int] = None, low: Optional[int] = None
    ) -> None:
        self._chan.set_write_buffer_limits(high=high, low=low)


async def serve_ssh(handlers: list, host: str = "127.0.0.1", port: int = 8022) -> None:
    import asyncssh

    key = asyncssh.generate_private_key("ssh-ed25519")
    mapping = build_mapping(handlers)

    class _DemoSSHServer(asyncssh.SSHServer):
        def password_auth_supported(self):
            return True
        def validate_password(self, username: str, password: str) -> bool:
            return True

    async def session_handler(process: asyncssh.SSHServerProcess) -> None:
        stdin = process.stdin
        stdout = process.stdout

        transport = SshTransport(stdin, stdout)
        protocol = make_server_protocol(mapping)
        protocol.connection_made(transport)
        transport._protocol = protocol

        print("[ssh-server] gRPC session started", file=sys.stderr)
        await pump(protocol, stdin)

    acceptor = await asyncssh.create_server(
        _DemoSSHServer,
        host,
        port,
        server_host_keys=[key],
        process_factory=session_handler,
        encoding=None,
    )
    print(f"[ssh-server] listening on {host}:{port}", file=sys.stderr)

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

    def __init__(self, reader: Any, writer: Any, **kwargs: Any):
        super().__init__(host="ssh", port=0, **kwargs)
        self._ssh_reader = reader
        self._ssh_writer = writer
        self._pump_task: asyncio.Task[None] | None = None
        self._ssh_transport: SshTransport | None = None

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        transport = SshTransport(self._ssh_reader, self._ssh_writer)
        self._ssh_transport = transport
        protocol.connection_made(transport)
        transport._protocol = protocol
        self._pump_task = asyncio.create_task(
            pump(protocol, self._ssh_reader), name="ssh-pump"
        )
        return protocol

    def close(self) -> None:
        super().close()
        if self._pump_task is not None and not self._pump_task.done():
            self._pump_task.cancel()
        if self._ssh_transport is not None:
            self._ssh_transport.close()
        self._ssh_writer.close()