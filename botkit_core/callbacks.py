"""Parsing and validating Telegram callback payloads.

Callback data arrives from the client. Telegram caps it at 64 bytes and imposes no
structure, so anything a handler parses out of it is untrusted input - a user can send
any byte string that starts with the right prefix by crafting a keyboard button or by
hand. The fleet had `int(callback.data.split(":")[1])` in 6 bots, which raises
`ValueError` on malformed data and, in `botkit-store`, was the first half of an IDOR:
the parsed `order_id` was then used to look up another user's data.
"""
from __future__ import annotations

MAX_CALLBACK_BYTES = 64


def parse_callback_int(data: str | None, prefix: str) -> int | None:
    """Return the integer argument of `"<prefix><n>"`, or None if it is not exactly that.

    Returns None rather than raising, so a handler can answer with a normal message
    instead of pushing a `ValueError` into the error middleware. Rejects anything with
    extra segments, whitespace, a sign, or more digits than an order id could plausibly
    have - `int()` alone would happily accept `"-1"`, `" 5"`, `"5:9"` and `"1_0"`.
    """
    if not data or not data.startswith(prefix):
        return None
    raw = data[len(prefix) :]
    if not raw or len(raw) > 18:  # > 18 digits cannot be a rowid
        return None
    if not raw.isascii() or not raw.isdigit():
        return None
    return int(raw)


def callback_is_wellformed(data: str | None, prefix: str) -> bool:
    """True when `data` is a well-formed `"<prefix><n>"` of legal length."""
    if data is not None and len(data.encode()) > MAX_CALLBACK_BYTES:
        return False
    return parse_callback_int(data, prefix) is not None


def parse_callback_int_at(data: str | None, prefix: str, index: int) -> int | None:
    """Return the integer in segment `index` of `"<prefix>seg:seg:n"`, or None.

    Payloads that carry more than the trailing id - `"book:date:12:2026-10-14"`,
    `"rem:confirm:delete:91"` - cannot be parsed by :func:`parse_callback_int`, which
    expects the whole remainder after the prefix to be a bare integer. This reads one
    named segment instead, and applies the same rules: ASCII digits only, no sign, no
    underscore, no whitespace, and a length a rowid cannot exceed.

    `index` counts colon-separated segments after `prefix`, so `0` is the first field.
    Out of range, malformed, or a prefix mismatch all return None rather than raising.
    """
    if not data or not data.startswith(prefix):
        return None
    parts = data[len(prefix) :].split(":")
    if index >= len(parts):
        return None
    raw = parts[index]
    if not raw or len(raw) > 18:
        return None
    if not raw.isascii() or not raw.isdigit():
        return None
    return int(raw)
