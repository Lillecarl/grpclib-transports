import asyncio
import sys

from demo import demo_grpc, demo_pb2
from grpclab.stdio import StdioChannel


def test_stdio_transport():
    async def run():
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "grpclab",
            "server",
            "--stdio",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        channel = StdioChannel(proc.stdout, proc.stdin)
        try:
            stub = demo_grpc.GreeterStub(channel)
            response = await stub.SayHello(
                demo_pb2.HelloRequest(name="Stdio")
            )
            assert response.message == "Hello, Stdio!"
        finally:
            channel.close()
            proc.kill()
            await proc.wait()

    asyncio.run(run())
