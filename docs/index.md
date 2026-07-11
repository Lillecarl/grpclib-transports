# grpclib-transports

gRPC over custom asyncio transports — stdio subprocess pipes, SSH sessions,
Unix-domain sockets, and multiprocessing pipe pairs.

```{toctree}
:maxdepth: 2
:caption: Contents

api
```

## Quick start

### Stdio (subprocess)

```python
import asyncio
from grpclib_transports import StdioChannel, serve_stdio

# Server side — runs inside a subprocess, speaks H2 over stdin/stdout
# serve_stdio([MyService()])

# Client side
async def main():
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "my_worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )
    channel = StdioChannel(proc.stdout, proc.stdin)
    # stub = MyStub(channel)
    # response = await stub.MyMethod(...)
```

### SSH

```python
from grpclib_transports import connect_ssh, serve_ssh

# Server
# await serve_ssh([MyService()], host="0.0.0.0", port=8022)

# Client
async with connect_ssh("localhost", port=8022, password="") as channel:
    ...
    # stub = MyStub(channel)
```

### Unix-domain socket

```python
from grpclib_transports import Server, connect_unix

# Server
server = Server([MyService()])
await server.start_unix("/tmp/my.sock")

# Client
channel = connect_unix("/tmp/my.sock")
```
