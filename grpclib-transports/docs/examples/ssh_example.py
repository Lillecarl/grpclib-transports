"""SSH transport — in-process server and client over SSH on a Unix socket.

Requires asyncssh.

Run with::

    python docs/examples/ssh_example.py
"""
from __future__ import annotations

import asyncio
import contextlib
import socket
import tempfile

import anyio
from greeter import greeter_grpc, greeter_pb2
from grpclib_transports import SshChannel, SshTransport
from grpclib_transports.example.server import Greeter
from grpclib_transports.protocol import serve_h2


async def main() -> None:
    import asyncssh

    sock = tempfile.mktemp(suffix=".sock")
    key = asyncssh.generate_private_key("ssh-ed25519")

    class _Server(asyncssh.SSHServer):
        def password_auth_supported(self):
            return True

        def validate_password(self, username, password):
            return True

    async def session_handler(stdin, stdout, _stderr):
        transport = SshTransport(stdin, stdout)
        await serve_h2([Greeter()], stdin, transport)

    ssock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    ssock.bind(sock)
    ssock.listen()
    try:
        acceptor = await asyncssh.listen(
            sock=ssock,
            server_host_keys=[key],
            server_factory=_Server,
            session_factory=session_handler,
            encoding=None,
            line_editor=False,
        )
        try:
            csock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            csock.connect(sock)
            conn = await asyncssh.connect(
                sock=csock,
                known_hosts=None,
                username="x",
                password="x",
            )
            try:
                stdin, stdout, _ = await conn.open_session(encoding=None)
                channel = SshChannel(stdout, stdin)
                stub = greeter_grpc.GreeterStub(channel)
                response = await stub.SayHello(greeter_pb2.HelloRequest(name="SSH"))
                assert response.message == "Hello, SSH!"
                print(f"Greeter replied: {response.message}")
            finally:
                await channel.aclose()
                conn.close()
        finally:
            acceptor.close()
            await acceptor.wait_closed()
    finally:
        with contextlib.suppress(OSError):
            await anyio.Path(sock).unlink()


if __name__ == "__main__":
    asyncio.run(main())
