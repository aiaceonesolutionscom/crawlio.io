"""In-memory lockout for the admin panel's username/password login — the one
endpoint in this codebase that authenticates with a guessable secret instead
of a signed third-party token (Clerk), so it's the one that actually needs
brute-force protection. Single-process/in-memory is fine for the current
single-VPS deployment; would need a shared store (Redis) behind a
multi-instance deployment.
"""
import time
from collections import defaultdict

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900.0  # 15 minutes

_failures: dict[str, list[float]] = defaultdict(list)


def is_locked_out(key: str) -> tuple[bool, float]:
    """Returns (locked, seconds_until_retry)."""
    now = time.monotonic()
    attempts = [t for t in _failures[key] if now - t < WINDOW_SECONDS]
    _failures[key] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        return True, max(WINDOW_SECONDS - (now - attempts[0]), 1.0)
    return False, 0.0


def record_failure(key: str) -> None:
    _failures[key].append(time.monotonic())


def record_success(key: str) -> None:
    _failures.pop(key, None)
