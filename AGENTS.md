# Version control

This repository uses Jujutsu (`jj`) for version control. Prefer `jj` commands
for status, diffs, history, and commit/change inspection. Do not assume a Git
workflow or run Git porcelain commands such as `git status`, `git diff`,
`git commit`, `git checkout`, or `git reset` unless the user explicitly asks for
Git or a tool requires Git-specific plumbing.

Run pytest commands so the complete output is preserved. Do not pipe pytest
directly into `tail`, `head`, `grep`, or similar filters. If you need a short
live summary, use `tee` first and enable `pipefail` so pytest failures are not
masked by `tail`, for example:

- `bash -o pipefail -c 'timeout 180 direnv exec . pytest tests 2>&1 | tee /tmp/pytest.log | tail -n 80'`

The saved log is the source of truth. Use the short live summary only to decide
what to inspect next, then query `/tmp/pytest.log` for the full failure context.
Do not use timeouts longer than 30 seconds for `grpclib-transports/tests`; these tests
should never take that long, and the shorter timeout catches hangs quickly.

# Python coding conventions

- Backward compatibility is not a concern in this repository. Do not preserve
  old APIs, exported names, behavior, or compatibility shims unless the user
  explicitly asks for compatibility in that specific task.

- Use `from __future__ import annotations` in Python modules that define or use
  type annotations.
- Module-level docstrings go **before** ``from __future__ import annotations``
  (they are the only code Python allows before a future import).
- Do not use string type hints such as `"Store"`. Use future annotations and
  `if TYPE_CHECKING:` imports instead.
- Keep imports at the top of the file. Lazy imports inside functions or methods
  are forbidden unless they are absolutely necessary to break a circular import
  cycle; prefer moving shared types to a neutral module over lazy imports.
- Import ordering:
  1. `from __future__ import annotations`
  2. standard library imports
  3. third-party imports
  4. local `nanopynix` imports
  5. `if TYPE_CHECKING:` block containing only type-only imports
  6. module constants
  7. code
- When re-exporting a name from another module, use the explicit re-export
  pattern `from module import Name as Name`. Consolidate related re-exports into
  one multi-line import block.
- Do not use `assert` statements outside `tests/`. For runtime validation, use
  explicit `if ...: raise ...`. To satisfy type checkers, prefer local variable
  aliasing or explicit `if value is None: raise ...` checks.
- Do not use `asyncio.get_event_loop()`. Use `asyncio.get_running_loop()` inside
  async code. For timestamps, use `time.monotonic()`.
- Keep a strong reference to background tasks created with
  `asyncio.create_task()`, for example in an instance `set` or `list`.
- Use `pathlib.Path` for filesystem paths that are not Nix daemon protocol
  strings. Convert to `str` as late as possible when crossing an API boundary.
- Do not hide unexpected failures with `except Exception: pass`. Log unexpected
  exceptions. Use `contextlib.suppress(...)` only for expected ignored
  exceptions, with a comment explaining why they are safe to ignore.

# Useful commands
- direnv exec . $command # run within a Nix environment with Python + dependencies configured
- nix build --no-link --print-out-paths --file . pkgs.python3Packages.h2.src # download and print location of h2 source (example package)
- direnv exec . ruff check --fix # run ruff and fix what it can
- direnv exec . pyright . # typechecking 
- timeout 30 direnv exec . pytest grpclib-transports/benchmarks # benchmark tests
- timeout 30 direnv exec . pytest grpclib-transports/tests # simple functionality tests
