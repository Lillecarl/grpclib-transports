from grpclib.protocol import H2Protocol


BUF_HIGH = pow(2, 19)  # 512 KiB — high watermark for write buffering
BUF_LOW = pow(2, 18)   # 256 KiB — low watermark for write buffering


async def pump(protocol: H2Protocol, reader) -> None:
    try:
        while True:
            data = await reader.read(BUF_HIGH)
            if not data:
                break
            protocol.data_received(data)
    except (ConnectionError, EOFError, OSError):
        pass
    finally:
        protocol.connection_lost(None)
