import argparse
import asyncio

from grpclib.server import Server

from grpclab.example.client import greet_ssh, greet_stdio, greet_unix
from grpclab.example.server import Greeter, serve
from grpclab.ssh import serve_ssh
from grpclab.stdio import serve_stdio


async def run_internal(path: str) -> None:
    server = Server([Greeter()])
    await server.start(path=path)
    try:
        await greet_unix(path)
    finally:
        server.close()
        await server.wait_closed()


def main() -> None:
    parser = argparse.ArgumentParser(prog="grpclab")
    sub = parser.add_subparsers(dest="command", required=True)

    p_server = sub.add_parser("server")
    p_server.add_argument("--unix-path", default=None)
    p_server.add_argument("--stdio", action="store_true")
    p_server.add_argument("--ssh", action="store_true")
    p_server.add_argument("--host", default="127.0.0.1")
    p_server.add_argument("--port", type=int, default=8022)

    p_client = sub.add_parser("client")
    p_client.add_argument("--unix-path", default=None)
    p_client.add_argument("--stdio", action="store_true")
    p_client.add_argument("--ssh", action="store_true")
    p_client.add_argument("--host", default="127.0.0.1")
    p_client.add_argument("--port", type=int, default=8022)
    p_client.add_argument("--username", default="demo")
    p_client.add_argument("--password", default="demo")

    p_internal = sub.add_parser("internal")
    p_internal.add_argument("--unix-path", default="/tmp/grpclab.sock")

    args = parser.parse_args()

    if args.command == "server":
        if args.ssh:
            asyncio.run(serve_ssh([Greeter()], args.host, args.port))
        elif args.stdio:
            asyncio.run(serve_stdio([Greeter()]))
        else:
            asyncio.run(serve(args.unix_path or "/tmp/grpclab.sock"))
    elif args.command == "client":
        if args.ssh:
            asyncio.run(greet_ssh(args.host, args.port, args.username, args.password))
        elif args.stdio:
            asyncio.run(greet_stdio())
        else:
            asyncio.run(greet_unix(args.unix_path or "/tmp/grpclab.sock"))
    elif args.command == "internal":
        asyncio.run(run_internal(args.unix_path))


if __name__ == "__main__":
    main()
