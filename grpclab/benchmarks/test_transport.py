import asyncio
import os
import socket
import sys
import time
import tempfile

import asyncssh
from demo import demo_grpc, demo_pb2
from grpclab.server import Greeter
from grpclab.stdio import StdioChannel
from grpclab.ssh import SshTransport, SshChannel, _make_server_protocol, _pump

from grpclib.server import Server as GrpcServer
from grpclib.client import Channel

SMALL_COUNT = 200
LARGE_COUNT = 5
LARGE_SIZE = 1024 * 1024
SMALL_PAYLOAD = b""
LARGE_PAYLOAD = os.urandom(LARGE_SIZE)


def _report(label, count, elapsed, payload_size):
    msgs_per_sec = count / elapsed
    total_bytes = count * payload_size
    mb_per_sec = total_bytes / elapsed / (1024 * 1024)
    print(f"\n  {label}:")
    print(f"    {count} msgs in {elapsed:.3f}s")
    print(f"    {msgs_per_sec:.0f} msgs/s  ({payload_size} B/msg)")
    if payload_size:
        print(f"    {mb_per_sec:.2f} MB/s")


async def _bench(label, payload, count, channel):
    stub = demo_grpc.GreeterStub(channel)
    req = demo_pb2.HelloRequest(name="bench", payload=payload)
    for i in range(count + 1):
        await stub.SayHello(req)
        if i == 0:
            start = time.perf_counter()
    elapsed = time.perf_counter() - start
    _report(label, count, elapsed, len(payload))


def _run(label, coro):
    try:
        asyncio.run(asyncio.wait_for(coro, timeout=30))
    except asyncio.TimeoutError:
        print(f"\n  [{label}] TIMEOUT after 30s")


def test_unix():
    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        server = GrpcServer([Greeter()])
        await server.start(path=sock)
        try:
            channel = Channel(path=sock)
            await _bench("unix (small)", SMALL_PAYLOAD, SMALL_COUNT, channel)
            await _bench("unix (large)", LARGE_PAYLOAD, LARGE_COUNT, channel)
            channel.close()
        finally:
            server.close()
            await server.wait_closed()
            try:
                os.unlink(sock)
            except OSError:
                pass
    _run("unix", run())


def test_stdio():
    async def run():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "grpclab", "server", "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        channel = StdioChannel(proc.stdout, proc.stdin)
        try:
            await _bench("stdio (small)", SMALL_PAYLOAD, SMALL_COUNT, channel)
            await _bench("stdio (large)", LARGE_PAYLOAD, LARGE_COUNT, channel)
        finally:
            channel.close()
            proc.kill()
            serr = await asyncio.wait_for(proc.stderr.read(), timeout=3)
            if serr:
                print(f"  [server stderr] {serr.decode()[:200]}")
    _run("stdio", run())


def test_ssh():
    class _Server(asyncssh.SSHServer):
        def password_auth_supported(self): return True
        def validate_password(self, u, p): return True

    async def run():
        sock = tempfile.mktemp(suffix=".sock")
        mapping = {}
        for h in [Greeter()]:
            mapping.update(h.__mapping__())
        key = asyncssh.generate_private_key("ssh-ed25519")
        ssock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ssock.bind(sock)
        ssock.listen(100)

        async def session_handler(process):
            t = SshTransport(process.stdin, process.stdout)
            p = _make_server_protocol(mapping)
            p.connection_made(t)
            t._protocol = p
            await _pump(p, process.stdin)

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
                await _bench("ssh (small)", SMALL_PAYLOAD, SMALL_COUNT, channel)
                await _bench("ssh (large)", LARGE_PAYLOAD, LARGE_COUNT, channel)
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
    _run("ssh", run())
