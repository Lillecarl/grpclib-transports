import contextlib
import socket
import tempfile

import anyio
import asyncssh
import pytest
from conftest import LARGE_COUNT, LARGE_PAYLOAD, SMALL_COUNT, SMALL_PAYLOAD, _bench, _run
from grpclab.example.server import Greeter
from grpclab.protocol import build_mapping, make_server_protocol, pump
from grpclab.ssh import SshChannel, SshTransport


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_ssh(parallelism):
    class _Server(asyncssh.SSHServer):
        def password_auth_supported(self): return True
        def validate_password(self, username, password): return True

    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        mapping = build_mapping([Greeter()])
        key = asyncssh.generate_private_key("ssh-ed25519")
        ssock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ssock.bind(sock)
        ssock.listen(100)

        async def session_handler(process):
            t = SshTransport(process.stdin, process.stdout)
            p = make_server_protocol(mapping)
            p.connection_made(t)
            t._protocol = p
            await pump(p, process.stdin)

        acceptor = await asyncssh.listen(
            sock=ssock, server_host_keys=[key], server_factory=_Server,
            process_factory=session_handler, encoding=None,
            encryption_algs=[
                "aes256-gcm@openssh.com", "aes128-gcm@openssh.com",
                "aes256-ctr", "aes192-ctr", "aes128-ctr",
                "chacha20-poly1305@openssh.com",
            ],
        )
        try:
            csock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            csock.connect(sock)
            conn = await asyncssh.connect(
                sock=csock, known_hosts=None, username="x", password="x",
                encryption_algs=[
                    "aes256-gcm@openssh.com", "aes128-gcm@openssh.com",
                    "aes256-ctr", "aes192-ctr", "aes128-ctr",
                    "chacha20-poly1305@openssh.com",
                ],
            )
            try:
                stdin, stdout, _ = await conn.open_session(encoding=None)
                channel = SshChannel(stdout, stdin)
                await _bench(f"ssh (small, p={parallelism})", SMALL_PAYLOAD, SMALL_COUNT, channel, parallelism=parallelism)
                await _bench(f"ssh (large, p={parallelism})", LARGE_PAYLOAD, LARGE_COUNT, channel, parallelism=parallelism)
                channel.close()
            finally:
                conn.close()
        finally:
            acceptor.close()
            await acceptor.wait_closed()
            with contextlib.suppress(OSError):
                await anyio.Path(sock).unlink()
    _run(f"ssh (p={parallelism})", run())
