import asyncio
import socket
import tempfile
import os

import asyncssh
from demo import demo_grpc, demo_pb2
from grpclab.server import Greeter
from grpclab.ssh import SshTransport, SshChannel
from grpclab.protocol import pump, make_server_protocol, build_mapping


class _TestSSHServer(asyncssh.SSHServer):
    def password_auth_supported(self):
        return True
    def validate_password(self, username, password):
        return True


def test_ssh_transport():
    sock_path = tempfile.mktemp(suffix=".sock")

    async def run():
        mapping = build_mapping([Greeter()])

        key = asyncssh.generate_private_key("ssh-ed25519")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(sock_path)
        sock.listen(100)

        async def session_handler(process):
            transport = SshTransport(process.stdin, process.stdout)
            protocol = make_server_protocol(mapping)
            protocol.connection_made(transport)
            transport._protocol = protocol
            await pump(protocol, process.stdin)

        acceptor = await asyncssh.listen(
            sock=sock,
            server_host_keys=[key],
            server_factory=_TestSSHServer,
            process_factory=session_handler,
            encoding=None,
        )
        try:
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(sock_path)

            conn = await asyncssh.connect(
                sock=client_sock,
                known_hosts=None,
                username="test",
                password="test",
            )
            try:
                stdin, stdout, stderr = await conn.open_session(
                    encoding=None
                )

                channel = SshChannel(stdout, stdin)
                stub = demo_grpc.GreeterStub(channel)
                response = await stub.SayHello(
                    demo_pb2.HelloRequest(name="SSH")
                )
                assert response.message == "Hello, SSH!"

                channel.close()
            finally:
                conn.close()
        finally:
            acceptor.close()
            await acceptor.wait_closed()

    try:
        asyncio.run(run())
    finally:
        try:
            os.unlink(sock_path)
        except OSError:
            pass
