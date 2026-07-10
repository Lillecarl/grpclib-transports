from grpclib.client import Channel
from demo import demo_pb2, demo_grpc


async def greet(path: str, name: str = "World") -> None:
    async with Channel(path=path) as channel:
        stub = demo_grpc.GreeterStub(channel)
        request = demo_pb2.HelloRequest(name=name)
        print(f"[client] sending: SayHello(name={request.name!r})")
        response = await stub.SayHello(request)
        print(f"[client] received: {response.message}")
