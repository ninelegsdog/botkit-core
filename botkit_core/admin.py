"""Admin authentication: password gate with attempt throttling.

The fleet has had three shapes of admin authentication, all of them copied from the
cookiecutter template and none of them enforced in every bot:

- some bots compared the password inline in the handler, with no attempt limit;
- some defined an ``AdminGate`` class and never called it from the router;
- one bot (``reminder``) did it properly and served as the model.

So a security fix to admin auth had to be applied by hand in nine repositories, and
was demonstrably missed. This module is the single home for that logic: import it
through the bots' existing ``src/core/auth.py`` shim and the behaviour stops
depending on which template a given bot was generated from.
"""
from __future__ import annotations

import hashlib
import hmac
import time


def _digest(password: str) -> str:
    """Hex sha256 of the password, used only for comparison.

    This is a length-leak fix, not a password store. There is no salt and no work factor:
    the value lives in process memory only, exactly as the plaintext did before, and the
    gate is single-process. Storing the plaintext and comparing digests removes the timing
    channel without pretending to be a KDF - which it is not, and which would change the
    constructor's contract for every caller.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class AdminGate:
    """Password gate for the admin surface, with a per-user attempt throttle.

    Callers should check :meth:`is_throttled` *before* :meth:`authorize`. The gate
    itself accepts a correct password even inside the throttle window - an admin who
    typed the right thing is not locked out - so the throttle only bounds how many
    guesses reach the comparison.

    Authorization is in-process memory: it does not survive a restart and does not
    span replicas. That is acceptable while every bot runs as a single process; if a
    bot is ever scaled out, this needs to move to the shared Redis the bots already
    depend on.
    """

    def __init__(
        self,
        password: str,
        admin_ids: list[int] | None = None,
        throttle_window: float = 300.0,
        max_attempts: int = 5,
    ) -> None:
        # Compared as a digest, never as the string. `hmac.compare_digest` returns as
        # soon as the lengths differ, so comparing raw passwords leaks the length of the
        # admin password to anyone able to time the response. Hashing first makes both
        # sides fixed-width and the comparison genuinely constant-time.
        self._password_hash = _digest(password)
        self._admin_ids = set(admin_ids or [])
        self._authorized: set[int] = set()
        self._attempts: dict[int, list[float]] = {}
        self._throttle_window = throttle_window
        self._max_attempts = max_attempts

    def is_admin(self, user_id: int) -> bool:
        """True for configured admins and for anyone the gate has authorised."""
        return user_id in self._admin_ids or user_id in self._authorized

    def authorize(self, user_id: int, password: str) -> bool:
        """Compare in constant time; on failure record the attempt."""
        if not hmac.compare_digest(_digest(password), self._password_hash):
            now = time.time()
            attempts = self._attempts.setdefault(user_id, [])
            attempts[:] = [t for t in attempts if now - t < self._throttle_window]
            attempts.append(now)
            return False
        self._authorized.add(user_id)
        self._attempts.pop(user_id, None)
        return True

    def deauthorize(self, user_id: int) -> None:
        self._authorized.discard(user_id)

    def is_throttled(self, user_id: int) -> bool:
        """True while this user is inside the throttle window after too many failures."""
        now = time.time()
        attempts = self._attempts.get(user_id, [])
        attempts[:] = [t for t in attempts if now - t < self._throttle_window]
        return len(attempts) >= self._max_attempts
