from __future__ import annotations

from pathlib import Path
from ssl import SSLContext
from typing import Any

from grpclib.client import Channel

from grpclib_transports.protocol import DEFAULT_TUNING, TransportTuning, make_config


def connect_unix(
    path: str | Path,
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
    **kwargs: Any,
) -> Channel:
    kwargs.setdefault("config", make_config(tuning))
    return Channel(path=str(path), **kwargs)


def connect_tcp(
    host: str,
    port: int,
    *,
    tuning: TransportTuning = DEFAULT_TUNING,
    ssl: SSLContext | bool | None = None,
    **kwargs: Any,
) -> Channel:
    kwargs.setdefault("config", make_config(tuning))
    return Channel(host=host, port=port, ssl=ssl, **kwargs)
