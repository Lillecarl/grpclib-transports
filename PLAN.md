# Plan: grpclab improvements

Goal: improve robustness, type-safety, and understandability of the grpclab
transport layer (stdio + ssh). The library code (transports, channels, pumps,
server helpers) should be cleanly separated from the demo application (Greeter
service, greet CLI, etc.).

## Fields

- **Description** — what to do and why
- **Considerations** — constraints, trade-offs, things to watch for
- **Status** — pending / in progress / done / skipped

---

## Task 1: Consolidate shared helpers into protocol.py

**Description**
Move duplicated H2 configuration, server-protocol factory, and handler-mapping
construction into `protocol.py`. Currently `_make_h2_config` and
`_make_server_protocol` live in `ssh.py` while `stdio.py` inlines the same
`H2Configuration`. The `mapping = {}; for h in handlers: mapping.update(...)`
pattern is copy-pasted 5+ times. Also separate the read-chunk size from the
write-buffer high watermark (`BUF_HIGH` serves double duty).

**Considerations**
- `protocol.py` currently only has `pump` and the buffer constants.
- Keep `_make_h2_config` / `_make_server_protocol` / `build_mapping` as
  module-level functions. They are import-time safe (no I/O).
- Tests and benchmarks import `_make_server_protocol` from `ssh.py` — update
  imports.
- Add a separate `READ_CHUNK` constant (same value as `BUF_HIGH` today, but
  semantically distinct) so future tuning is independent.

**Status**: done — Moved `make_h2_config`, `make_server_protocol`, and
`build_mapping` into `protocol.py`. Added `READ_CHUNK` constant separate
from `BUF_HIGH`. Removed duplicated inline H2 config from `stdio.py` and
`_make_h2_config`/`_make_server_protocol` from `ssh.py`. Updated all test
and benchmark imports. Also fixed the dead `EOFError` catch in `pump`
(R2/Task 4 partial) as part of the rewrite.

---

## Task 2: Extract BaseCustomTransport, remove StreamReaderWriterTransport

**Description**
`SshTransport`, `StdioTransport`, and the unused `StreamReaderWriterTransport`
share ~70% identical code: `close`, `is_closing`, `abort`,
`get_protocol`/`set_protocol`, `pause_reading`/`resume_reading`, `write`.
Extract a `BaseCustomTransport(asyncio.Transport)` into `protocol.py` and
have concrete transports override only what differs. Remove
`StreamReaderWriterTransport` entirely — per the user, stdio and ssh are the
only transports we care about, and the stream-reader-writer transport was a
pre-specialisation stepping stone.

**Considerations**
- `StdioChannel._create_connection` currently has `transport: Optional`
  fallback that creates a `StreamReaderWriterTransport` — remove this
  branch since `StdioChannel` now always receives a proper transport.
- Don't move flow-control overrides (`_on_pause_writing`, `_Bridge`) into the
  base — those are transport-specific.
- `_protocol` field should be on the base class.

**Status**: done — Extracted `BaseCustomTransport(asyncio.Transport)` into
`protocol.py` with shared `is_closing`, `get_protocol`/`set_protocol`,
`pause_reading`/`resume_reading`, and the `_protocol`/`_closing` fields.
Removed `StreamReaderWriterTransport` entirely. `StdioTransport` and
`SshTransport` now subclass `BaseCustomTransport` and override only their
specific methods. `StdioChannel._create_connection` no longer has the
fallback branch — it always creates a `StdioTransport` using the reader/
writer. Added proper type annotations to transport methods, channels, and
`serve_stdio`/`serve_ssh` params. Tasks 2 and 3 combined since the rewrite
naturally handled both.

---

## Task 3: Type transports properly

**Description**
Add proper type annotations to the transport classes and channel subclasses.

- `_protocol: Optional[asyncio.Protocol]` → `_protocol: Optional[H2Protocol]`
  (grpclib's `H2Protocol` does not subclass `asyncio.Protocol` but that's what
  the field holds).
- `handlers: list` → `Sequence[IServable]` in `serve_ssh`, `serve_stdio`,
  `build_mapping`.
- `mapping: dict` → `Mapping[str, const.Handler]`.
- Type all transport method signatures: `write(self, data: bytes)`,
  `get_extra_info(self, name: str, default: Any = None)`, etc.
- `**kwargs: Any` in channel `__init__`.

**Considerations**
- `grpclib._typing.IServable` is a `Protocol` with `__mapping__`.
- grpclib's `BaseTransport` is the minimal interface the `Connection` calls
  against; our transports subclass `asyncio.Transport` which is technically
  type-discordant but works by duck-typing. We keep `asyncio.Transport` for
  now (matches existing tests) but annotate the `_protocol` field accurately.
- Don't fight pyright on every override signature — focus on the field types
  and function signatures that matter for the public surface.

**Status**: pending

---

## Task 4: Fix pump to pass exceptions and remove dead catch

**Description**
`pump` always calls `protocol.connection_lost(None)` even when an exception
propagated. Capture the exception and pass it: it may help grpclib's
processor log or clean up streams. Also remove the `EOFError` catch —
`StreamReader.read` doesn't raise `EOFError`.

**Considerations**
- `connection_lost(exc)` currently just calls `self.processor.close(reason=...)`.
- Use `BaseException` (like grpclib's own signature) or `Optional[BaseException]`.
- The broad `except (ConnectionError, EOFError, OSError)` should drop `EOFError`.

**Status**: done — `pump` now captures the exception from `ConnectionError`/
`OSError` and passes it to `protocol.connection_lost(exc)` instead of always
`None`. The dead `EOFError` catch was already removed in Task 1.

---

## Task 5: Fix channel lifecycle — cancel pump task, close writer on close

**Description**
`SshChannel` and `StdioChannel` create `asyncio.create_task(pump(...))` and
discard the reference. On `channel.close()` the reader is never cancelled and
the task lingers. The underlying SSH session / stdio writer is also left open
because grpclib's `Channel.close()` only touches `self._protocol`.

Override `close()` in channel subclasses to:
1. Cancel the pump task.
2. Close the underlying writer / SSH session.

**Considerations**
- grpclib's `Channel.close()` deletes `self._protocol` and resets state. Call
  `super().close()` first, then do our cleanup.
- The pump task should be created with a name for debuggability.
- Make sure tests still pass — `test_stdio` does `channel.close()` + `proc.kill()`.

**Status**: done — Both `SshChannel` and `StdioChannel` now store the pump
task and transport reference. `close()` calls `super().close()` first (which
cleans up grpclib's protocol), then cancels the pump task if not done, then
closes the underlying transport/writer. Pump tasks are named (`"ssh-pump"`,
`"stdio-pump"`) for debuggability in task stack dumps.

---

## Task 6: Fix abort to be a real hard reset

**Description**
`abort()` is currently `self._writer.close()` which is a graceful drain, not
a hard reset. For `SshTransport` use `self._writer.abort()` (asyncssh supports
it). For stdio there's no hard abort on pipes — just close, so keep `close()`
but document that stdio abort is best-effort.

**Considerations**
- `asyncssh.SSHWriter` has `abort()` which closes the channel abruptly.
- `asyncio.Transport.abort()` signature returns `None`.
- Don't break the `_closing` flag logic.

**Status**: done — `SshTransport.abort()` was already using
`self._writer.abort()` (asyncssh hard reset). Added a comment on
`StdioTransport.abort()` noting that pipes have no hard abort so `close()`
is the best we can do. No code change needed for SSH.

---

## Task 7: Fix SshTransport flow-control — restore session methods on close

**Description**
`SshTransport.__init__` monkey-patches `session.pause_writing` and
`session.resume_writing` with no teardown to restore them. This permanently
mutates the asyncssh session and breaks on upgrades. Store the originals and
restore them in `close()` / `abort()`.

**Considerations**
- The monkey-patch is on `writer._session` (asyncssh `SSHStreamSession`).
- Need to call the original session methods from our overrides — already done
  via `_orig_pause_writing()` / `_orig_resume_writing()`.
- Keep the same approach but add `_restore_session_callbacks()` called from
  `close()` and `abort()`.
- The flow-control forwarding is essential for backpressure; can't remove it.

**Status**: done — Added `_restore_session_callbacks()` to `SshTransport`
that restores the original `pause_writing`/`resume_writing` on the asyncssh
session. Called from both `close()` and `abort()`. The original callbacks
are stored as `self._orig_pause_writing`/`self._orig_resume_writing` and
set to `None` after restoration to prevent double-restore.

---

## Task 8: Add graceful shutdown to serve_ssh

**Description**
`serve_ssh` does `await asyncio.Event().wait()` which blocks forever, ignores
SIGINT/SIGTERM, and never closes the acceptor or keys. Add signal handlers
matching `serve()` in `server.py` and close the asyncssh acceptor on shutdown.

**Considerations**
- `asyncssh.create_server` returns a server factory; need to capture and close
  it.
- Signal handlers must be guarded against double-fire (see Task 9).
- The SSH server generates a key on every start; cleanup isn't needed for that.
- The acceptor's `close()` + `wait_closed()` pattern mirrors the test cleanup.

**Status**: pending

---

## Task 9: Guard signal handler against double-fire

**Description**
`server.py:25-26` registers both SIGINT and SIGTERM to `stop.set_result(None)`.
If both fire, the second raises `InvalidStateError`. Guard with
`if not stop.done(): stop.set_result(None)`.

**Considerations**
- Trivial fix but important for robustness in signal-heavy environments.
- Apply the same guard in `serve_ssh` (Task 8) since it adds its own handlers.

**Status**: pending

---

## Task 10: Split library from demo, define public API, unify greet

**Description**
`server.py`, `client.py`, `ssh.py`, and `__main__.py` all `from demo import
...`. For a transport-plumbing library the `Greeter` service belongs in an
example/demo package. Restructure:

- Move `Greeter` and `serve()` into `grpclab/example/server.py`.
- Move `greet()` into `grpclab/example/client.py`.
- Move the CLI (`__main__.py`) into the example package.
- Define public API in `grpclab/__init__.py`: `StdioChannel`, `StdioTransport`,
  `serve_stdio`, `SshChannel`, `SshTransport`, `serve_ssh`, `pump`,
  `build_mapping`, etc.
- Unify the three `greet_*` functions into one `greet(channel, name="World")`
  used by all CLI subcommands.

**Considerations**
- Tests import from `grpclab.server`, `grpclab.client`, `grpclab.ssh`,
  `grpclab.stdio`, `grpclab.protocol` — update test imports accordingly.
- Benchmarks import from `grpclab.server` and `grpclab.protocol` too.
- The `serve()` function in `server.py` uses `demo` → move with `Greeter`.
- `__main__.py` imports from `.server`, `.client`, `.stdio`, `.ssh` — split
  imports between library and example.
- `greet_stdio` is defined inline in `__main__.py` — fold into unified `greet`.
- `greet_ssh` does a late `from demo import ...` inside the function — move
  to top of the example module.
- Keep unix-socket greet working by using `grpclib.Channel` directly in the
  example client.

**Status**: pending

---

## Task 11: Declare dependencies in pyproject.toml

**Description**
`pyproject.toml:13` declares `dependencies = []` but every module imports
`grpclib`/`h2` and `ssh.py`/`__main__.py` import `asyncssh`. Declare them
properly. `asyncssh` can be in optional extras if desired, but since ssh is a
core transport we care about, keep it as a direct dependency.

**Considerations**
- `grpclib` and `h2` are always required.
- `asyncssh` is always required for the ssh transport.
- This won't affect nix-based development (nix provides deps) but matters for
  anyone installing via pip.
- Python >=3.12 is already declared.

**Status**: pending

---

## Task 12: Clean up minor issues

**Description**
- `__main__.py:28,30` uses `__import__("sys").stderr` — use a normal `import
  sys` at top.
- Test/benchmark files use `tempfile.mktemp` (deprecated, racey) — use
  `tempfile.mkdtemp` or accept it for tests (low priority).
- Late `from demo import ...` inside `greet_ssh` — will be fixed by Task 10
  restructuring.
- Remove the `BUF_LOW` import from `ssh.py` if it's unused there (ssh uses
  `BUF_HIGH`/`BUF_LOW` for channel set_write_buffer_limits).

**Considerations**
- These are minor; combine into one commit.
- Don't fix tempfile.mktemp in tests — it's harmless in tests and
  over-scoped for this pass.

**Status**: pending