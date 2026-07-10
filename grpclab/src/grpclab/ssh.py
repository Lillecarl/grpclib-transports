import asyncio
import sys
from typing import Optional

from h2.config import H2Configuration
from grpclib.config import Configuration
from grpclib.protocol import H2Protocol
from grpclib import client
from grpclib.server import Handler as ServerHandler
from grpclib.events import _DispatchServerEvents
from grpclib.encoding.proto import ProtoCodec


_CHANNEL_BUF_HIGH = 65536
_CHANNEL_BUF_LOW = 32768


class SshTransport(asyncio.Transport):

    def __init__(self, reader, writer):
        super().__init__()
        self._reader = reader
        self._writer = writer
        self._protocol: Optional[asyncio.Protocol] = None
        self._closing = False

        chan = writer._chan
        chan.set_write_buffer_limits(high=_CHANNEL_BUF_HIGH, low=_CHANNEL_BUF_LOW)
        self._chan = chan
        self._write_paused = False

    def write(self, data: bytes) -> None:
        self._writer.write(data)
        if self._write_paused:
            if self._chan.get_write_buffer_size() <= self._chan._send_low_water:
                self._write_paused = False
                if self._protocol is not None:
                    self._protocol.resume_writing()
        elif self._chan.get_write_buffer_size() > self._chan._send_high_water:
            self._write_paused = True
            if self._protocol is not None:
                self._protocol.pause_writing()

    def get_write_buffer_size(self) -> int:
        return self._chan.get_write_buffer_size()

    def close(self) -> None:
        self._closing = True
        self._writer.close()

    def is_closing(self) -> bool:
        return self._closing

    def get_extra_info(self, name, default=None):
        if name in ("username", "session", "channel"):
            return self._writer.get_extra_info(name)
        return self._chan.get_extra_info(name, default)

    def get_protocol(self):
        return self._protocol

    def set_protocol(self, protocol):
        self._protocol = protocol

    def abort(self):
        self._closing = True
        self._writer.abort()

    def can_write_eof(self):
        return self._chan.can_write_eof()

    def write_eof(self):
        self._writer.write_eof()

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass

    def set_write_buffer_limits(self, high=None, low=None):
        self._chan.set_write_buffer_limits(high=high, low=low)


async def _pump(protocol: H2Protocol, reader) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            protocol.data_received(data)
    except (ConnectionError, EOFError, OSError):
        pass
    finally:
        protocol.connection_lost(None)


def _make_h2_config(*, client_side: bool) -> H2Configuration:
    return H2Configuration(
        client_side=client_side,
        header_encoding="ascii",
        validate_inbound_headers=False,
        validate_outbound_headers=False,
        normalize_inbound_headers=False,
        normalize_outbound_headers=False,
    )


def _make_server_protocol(
    mapping: dict,
) -> H2Protocol:
    config = Configuration().__for_server__()
    h2_config = _make_h2_config(client_side=False)
    handler = ServerHandler(mapping, ProtoCodec(), None, _DispatchServerEvents())
    return H2Protocol(handler, config, h2_config)


async def serve_ssh(handlers: list, host: str = "127.0.0.1", port: int = 8022) -> None:
    import asyncssh

    key = asyncssh.generate_private_key("ssh-ed25519")

    mapping = {}
    for h in handlers:
        mapping.update(h.__mapping__())

    class _DemoSSHServer(asyncssh.SSHServer):
        def password_auth_supported(self):
            return True
        def validate_password(self, username: str, password: str) -> bool:
            return True

    async def session_handler(process: asyncssh.SSHServerProcess) -> None:
        stdin = process.stdin
        stdout = process.stdout

        transport = SshTransport(stdin, stdout)
        protocol = _make_server_protocol(mapping)
        protocol.connection_made(transport)
        transport._protocol = protocol

        print("[ssh-server] gRPC session started", file=sys.stderr)
        await _pump(protocol, stdin)

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

    def __init__(self, reader, writer, **kwargs):
        super().__init__(host="ssh", port=0, **kwargs)
        self._ssh_reader = reader
        self._ssh_writer = writer

    async def _create_connection(self) -> H2Protocol:
        protocol = self._protocol_factory()
        transport = SshTransport(self._ssh_reader, self._ssh_writer)
        protocol.connection_made(transport)
        transport._protocol = protocol
        asyncio.create_task(_pump(protocol, self._ssh_reader))
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
