"""The admin password must not leak its length through the comparison.

`hmac.compare_digest` returns as soon as the two operands differ in length. Comparing the
raw password against the raw expected password therefore told an attacker who could time a
response how long the admin password is. The gate now compares sha256 digests, which are
fixed width, so the comparison is genuinely constant-time.

`reminder` already did this - it has no password in the gate at all and verifies separately
against a hash. The other eight bots went through this shared class, so fixing it here fixes
all of them at once, which is the point of the module being shared.

These tests do not try to measure timing. Timing assertions are the classic flaky test: they
fail on a loaded machine and pass on a broken implementation. What is asserted instead is the
property that makes timing irrelevant - what is stored and compared is fixed width, and does
not depend on the secret.
"""
from __future__ import annotations

import inspect
import re

import pytest

from botkit_core.admin import AdminGate, _digest


def test_the_gate_never_stores_the_plaintext() -> None:
    """A password attribute holding the secret itself is the thing being removed."""
    gate = AdminGate("hunter2-correct-horse", [])
    values = [v for v in vars(gate).values() if isinstance(v, str)]
    assert "hunter2-correct-horse" not in values, (
        f"the gate still holds the plaintext password: {values}"
    )


def test_comparison_is_over_fixed_width_digests() -> None:
    """What is compared must not vary in length with the secret."""
    short = AdminGate("a", [])
    long = AdminGate("a" * 256, [])
    stored = {
        len(v) for gate in (short, long)
        for k, v in vars(gate).items()
        if "password" in k and isinstance(v, str)
    }
    assert len(stored) == 1, f"stored digest length varies with the password: {stored}"
    assert stored.pop() == 64, "expected a hex sha256 digest"

    for attempt in ("a", "a" * 256, "", "x"):
        assert len(_digest(attempt)) == 64


def test_source_does_not_compare_raw_passwords() -> None:
    """Belt and braces: the compare must be digest-to-digest."""
    src = inspect.getsource(AdminGate.authorize)
    assert "compare_digest(_digest(" in src, (
        "authorize must compare digests; it currently looks like:\n" + src
    )
    assert re.search(r"compare_digest\(\s*password\b", src) is None, (
        "authorize is comparing the raw password, which leaks its length"
    )


def test_authorisation_behaviour_is_unchanged() -> None:
    """The leak fix must not change a single answer."""
    gate = AdminGate("correct-horse", [7])

    assert gate.authorize(1, "correct-horse") is True
    assert gate.is_admin(1) is True

    gate.deauthorize(1)
    assert gate.is_admin(1) is False

    assert gate.authorize(1, "wrong") is False
    assert gate.is_admin(1) is False

    # Case and surrounding whitespace are still just different strings.
    assert gate.authorize(1, "Correct-horse") is False
    assert gate.authorize(1, " correct-horse") is False
    assert gate.authorize(1, "") is False

    # Configured admins pass without any password.
    assert gate.is_admin(7) is True


def test_throttle_still_works_after_the_change() -> None:
    """The compare sits inside the throttle path; both must still hold."""
    gate = AdminGate("correct-horse", [])
    for _ in range(5):
        gate.authorize(1, "wrong")
    assert gate.is_throttled(1) is True
    # A correct password still succeeds inside the throttle window.
    assert gate.authorize(1, "correct-horse") is True
    assert gate.is_throttled(1) is False


@pytest.mark.parametrize(
    "password", ["", " ", "юникод-пароль", "a" * 10_000, "🔑"]
)
def test_digest_handles_whatever_arrives(password: str) -> None:
    assert len(_digest(password)) == 64

