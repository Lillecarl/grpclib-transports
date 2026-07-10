import os
import socket
import tempfile

import asyncssh
import pytest

from conftest import SMALL_PAYLOAD, LARGE_PAYLOAD, SMALL_COUNT, LARGE_COUNT, _bench, _run

from grpclab.server import Greeter
from grpclab.protocol import pump, make_server_protocol, build_mapping
from grpclab.ssh import SshTransport, SshChannel


@pytest.mark.parametrize("parallelism", [1, 2, 4, 8])
def test_ssh(parallelism):
    class _Server(asyncssh.SSHServer):
        def password_auth_supported(self): return True
        def validate_password(self, u, p): return True

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
        )
        try:
            csock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            csock.connect(sock)
            conn = await asyncssh.connect(
                sock=csock, known_hosts=None, username="x", password="x",
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
            try:
                os.unlink(sock)
            except OSError:
                pass
    _run(f"ssh (p={parallelism})", run())
