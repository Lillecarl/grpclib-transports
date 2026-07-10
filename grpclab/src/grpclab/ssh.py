import asyncio
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
)


class SshTransport(BaseCustomTransport):

    def __init__(self, reader: Any, writer: Any):
        super().__init__()
        self._reader = reader
        self._writer = writer

        chan = writer._chan
        chan.set_write_buffer_limits(high=BUF_HIGH, low=BUF_LOW)
        self._chan = chan

        session = writer._session
        self._orig_pause_writing = session.pause_writing
        self._orig_resume_writing = session.resume_writing
        session.pause_writing = self._on_pause_writing
        session.resume_writing = self._on_resume_writing

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
        self._writer.close()

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        if name in ("username", "session", "channel"):
            return self._writer.get_extra_info(name)
        return self._chan.get_extra_info(name, default)

    def abort(self) -> None:
        self._closing = True
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

    await asyncssh.create_server(
        _DemoSSHServer,
        host,
        port,
        server_host_keys=[key],
        process_factory=session_handler,
        encoding=None,
    )
    print(f"[ssh-server] listening on {host}:{port}", file=sys.stderr)
    await asyncio.Event().wait()


class SshChannel(client.Channel):

    def __init__(self, reader: Any, writer: Any, **kwargs: Any):
        super().__init__(host="ssh", port=0, **kwargs)
        self._ssh_reader = reader
        self._ssh_writer = writer

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        transport = SshTransport(self._ssh_reader, self._ssh_writer)
        protocol.connection_made(transport)
        transport._protocol = protocol
        asyncio.create_task(pump(protocol, self._ssh_reader))
        return protocol


async def greet_ssh(
    host: str = "127.0.0.1",
    port: int = 8022,
    username: str = "demo",
    password: str = "demo",
) -> None:
    import asyncssh

    async with asyncssh.connect(
        host,
        port,
        username=username,
        password=password,
        known_hosts=None,
    ) as conn:
        stdin, stdout, stderr = await conn.open_session(encoding=None)
        channel = SshChannel(stdout, stdin)
        from demo import demo_grpc, demo_pb2
        try:
            stub = demo_grpc.GreeterStub(channel)
            request = demo_pb2.HelloRequest(name="World")
            print(f"[client] sending: SayHello(name={request.name!r})", file=sys.stderr)
            response = await stub.SayHello(request)
            print(f"[client] received: {response.message}", file=sys.stderr)
        finally:
            channel.close()