import asyncio
import contextlib
import os
import socket
import tempfile
from pathlib import Path
from typing import Any

import asyncssh
from greeter import greeter_grpc, greeter_pb2
from grpclib_transports.example.server import Greeter
from grpclib_transports.protocol import DEFAULT_TUNING, serve_h2
from grpclib_transports.ssh import SshTransport, connect_ssh


class _TestSSHServer(asyncssh.SSHServer):
    def password_auth_supported(self):
        return True

    def validate_password(self, username: str, password: str):
        return True


def test_ssh_transport():
    fd, sock_path = tempfile.mkstemp(suffix=".sock")
    os.close(fd)
    Path(sock_path).unlink()

    async def run():
        key = asyncssh.generate_private_key("ssh-ed25519")  # pyright: ignore[reportUnknownMemberType] -- asyncssh type stubs are incomplete
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, DEFAULT_TUNING.buffer_size)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, DEFAULT_TUNING.buffer_size)
        sock.bind(sock_path)
        sock.listen(100)

        async def session_handler(stdin: Any, stdout: Any, _stderr: Any):
            transport = SshTransport(stdin, stdout)
            await serve_h2([Greeter()], stdin, transport)

        acceptor = await asyncssh.listen(
            sock=sock,
            server_host_keys=[key],
            server_factory=_TestSSHServer,
            session_factory=session_handler,
            encoding=None,
            line_editor=False,
            encryption_algs=[
                "aes256-gcm@openssh.com",
                "aes128-gcm@openssh.com",
                "aes256-ctr",
                "aes192-ctr",
                "aes128-ctr",
                "chacha20-poly1305@openssh.com",
            ],
        )
        try:
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(sock_path)

            async with connect_ssh(
                "localhost",
                known_hosts=None,
                username="test",
                password="test",
                sock=client_sock,
                encryption_algs=[
                    "aes256-gcm@openssh.com",
                    "aes128-gcm@openssh.com",
                    "aes256-ctr",
                    "aes192-ctr",
                    "aes128-ctr",
                    "chacha20-poly1305@openssh.com",
                ],
            ) as channel:
                stub = greeter_grpc.GreeterStub(channel)
                response = await stub.SayHello(greeter_pb2.HelloRequest(name="SSH"))
                assert response.message == "Hello, SSH!"
        finally:
            acceptor.close()
            await acceptor.wait_closed()

    try:
        asyncio.run(run())
    finally:
        with contextlib.suppress(OSError):
            Path(sock_path).unlink()
