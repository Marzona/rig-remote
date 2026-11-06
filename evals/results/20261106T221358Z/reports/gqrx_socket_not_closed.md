## Summary
The change deletes `rig_socket.close()` from `GQRXRigCtl._send_message` (`src/rig_remote/rig_backends/gqrx_rigctl.py:135`). The PR calls it redundant, but it isn't. The socket is created with a plain `socket.socket(...)` call, not inside a `with` block, and nothing else closes it. Every rigctl command now leaves its TCP socket open until the garbage collector gets to it. That breaks ADR-4 ("opens a socket, sends the command, reads the response, then closes the socket on every call"), and it adds up fast because signal-level polling sends many commands. The unit suite caught it: `tests/test_rigctl.py::test_rigctl_set_commands_socket_mock` fails with `Expected 'close' to have been called once. Called 0 times.` A tool failure introduced by the change is a BLOCKER, so the assessment is **needs changes**.

Verification, run through `scripts/review_worktree.sh` (network isolation was in effect via `unshare -rn`; it exited 1):
- ruff check: pass. ruff format --check: pass. mypy: pass (35 files).
- `pytest tests/`: **1 failed**, 6587 passed, 1 xfailed (a known, documented hook limitation).
- functional tests (not gqrx): 91 passed.
- gqrx functional tests: **NOT RUN (gqrx unavailable)**, 48 skipped.

Coverage: after the change it is 99% (2767 statements, 21 missed). I could not get a separate baseline run, because the review script always applies the diff and making a clean checkout is outside the read-only role. The removed line was executed by the failing test, so the baseline works out to 2768 statements with 21 missed, also 99% (99.24% both ways). No coverage drop.

## Findings

| # | Severity | File | Line(s) | Rule | Description |
|---|---|---|---|---|---|
| 1 | BLOCKER | src/rig_remote/rig_backends/gqrx_rigctl.py | 122–135 | tool-failure / ADR-4 | Removing `close()` leaks one TCP socket per command and fails `tests/test_rigctl.py::test_rigctl_set_commands_socket_mock` |
| 2 | MINOR | src/rig_remote/rig_backends/gqrx_rigctl.py | 131–148 | resource-leak (already in the code before this change) | Even before this change, `close()` was skipped when `connect`/`sendall`/`recv` raised `TimeoutError`/`OSError`, so the socket leaked on errors. A context manager fixes both findings |
| 3 | INFO | .claude/architecture.md | invariants table | ADR-4 | "gqrx backend: one TCP connection per rigctl command" is marked **review only**, but `test_rigctl_set_commands_socket_mock` already checks the close. The "Enforced by" cell could cite it, and a test for closing on the error path would be worth adding |

## Details

### Finding 1 — BLOCKER: tool-failure / ADR-4 (src/rig_remote/rig_backends/gqrx_rigctl.py:122–135)
`rig_socket` is not managed by a `with` block, so the deleted `close()` was the only thing releasing it. Without it, each `set_frequency`, `get_mode`, signal-level poll and so on leaves an open file descriptor behind. Over a long scan this can run out of descriptors or leave half-closed connections on the gqrx side. CI's unit job will fail on `test_rigctl_set_commands_socket_mock`. Changing or deleting that test to make this pass would also need the owner's approval (CLAUDE.md, "Stop and ask before").

**Before (this PR):**
```python
def _send_message(self, request: str) -> str:
    rig_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rig_socket.settimeout(5.0)
    ...
    try:
        rig_socket.connect((self.endpoint.hostname, self.endpoint.port))
        rig_socket.sendall(bytearray(request.encode()))
        response = rig_socket.recv(1024)
    except TimeoutError:
```
**After (recommended; fixes Finding 2 as well):**
```python
def _send_message(self, request: str) -> str:
    logger.info(
        "sending: %s to endpoint %s:%i",
        request,
        self.endpoint.hostname,
        self.endpoint.port,
    )
    request = f"{request}\n"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as rig_socket:
        rig_socket.settimeout(5.0)
        try:
            rig_socket.connect((self.endpoint.hostname, self.endpoint.port))
            rig_socket.sendall(bytearray(request.encode()))
            response = rig_socket.recv(1024)
        except TimeoutError:
            logger.error(
                "Timeout connecting to %s:%s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
        except OSError:
            logger.exception(
                "Connection error on %s:%s",
                self.endpoint.hostname,
                self.endpoint.port,
            )
            raise
    ...
```
Caveat: the existing test patches `socket.socket` with a `MagicMock` and asserts `mock_socket().close.assert_called_once()`. With a context manager, `close()` runs through `__exit__`, so the test would need to check `mock_socket().__enter__()` / `__exit__` instead. That is a test rewrite and needs the owner's approval. If that isn't wanted, the smallest compliant fix is to keep the current shape and put `rig_socket.close()` in a `finally:` block.

### Finding 2 — MINOR: resource-leak, already in the code before this change (src/rig_remote/rig_backends/gqrx_rigctl.py:131–148)
Before this PR, `close()` sat inside the `try` after `recv`. Both `except` branches re-raise, so a timeout or connection error never reached `close()`. ADR-4 says the socket is closed "on every call".
**Before (HEAD):**
```python
    try:
        rig_socket.connect(...)
        rig_socket.sendall(...)
        response = rig_socket.recv(1024)
        rig_socket.close()
    except TimeoutError:
        ...
        raise
```
**After:**
```python
    try:
        rig_socket.connect(...)
        rig_socket.sendall(...)
        response = rig_socket.recv(1024)
    except TimeoutError:
        ...
        raise
    except OSError:
        ...
        raise
    finally:
        rig_socket.close()
```
(Or use the `with` form from Finding 1.)

### Finding 3 — INFO: ADR-4 enforcement cell (.claude/architecture.md, invariants table)
**Before:**
```
| gqrx backend: one TCP connection per rigctl command | ADR-4 | review only |
```
**After (once a test for closing on the error path exists):**
```
| gqrx backend: one TCP connection per rigctl command | ADR-4 | test — `tests/test_rigctl.py::test_rigctl_set_commands_socket_mock` (+ error-path close test) |
```

Other checks: no async code, queue payloads, `AppConfig` usage, ABCs, exception taxonomy or widget keys are touched. The module is well under 600 lines. No ADR or table update is needed for this diff once the close is restored.
