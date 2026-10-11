"""Callback payloads are client-controlled; the parser must reject anything but "<prefix><n>"."""
from __future__ import annotations

import pytest

from botkit_core.callbacks import callback_is_wellformed, parse_callback_int


@pytest.mark.parametrize(
    ("data", "prefix", "expected"),
    [
        ("store_redeliver:1", "store_redeliver:", 1),
        ("store_redeliver:4242", "store_redeliver:", 4242),
        ("store_redeliver:0", "store_redeliver:", 0),
        # A payload bigger than any rowid is rejected rather than parsed.
        ("store_redeliver:" + "9" * 19, "store_redeliver:", None),
    ],
)
def test_accepts_exactly_prefix_plus_digits(
    data: str, prefix: str, expected: int | None
) -> None:
    assert parse_callback_int(data, prefix) == expected


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "store_redeliver:",  # no argument
        "store_redeliver",  # prefix missing the separator
        "store_cart:1",  # wrong prefix
        "store_redeliver:-1",  # sign
        "store_redeliver: 5",  # leading space - int() would accept this
        "store_redeliver:5:9",  # extra segment - split()[1] would silently take 5
        "store_redeliver:1_0",  # underscore - int() accepts this as 10
        "store_redeliver:0x10",  # hex-ish
        "store_redeliver:٥",  # non-ASCII digit - int() accepts these too
        "store_redeliver:1.0",  # float-ish
        "store_redeliver:+7",  # explicit plus
        "STORE_REDELIVER:1",  # case: prefix is case sensitive, so this must miss
    ],
)
def test_rejects_everything_that_is_not_a_bare_positive_integer(data: str | None) -> None:
    """Every case here would have raised, silently mis-parsed, or been accepted by `int()`.

    The point of the negative list is that `int(callback.data.split(":")[1])` handles
    none of them correctly: it raises ValueError, or worse, returns a wrong number.
    """
    assert parse_callback_int(data, "store_redeliver:") is None


def test_wellformed_also_checks_the_64_byte_limit() -> None:
    assert callback_is_wellformed("store_redeliver:1", "store_redeliver:")
    # 64 bytes is Telegram's cap for callback_data; over it the button could never exist.
    over = "store_redeliver:" + "1" * 50
    assert len(over.encode()) > 64
    assert callback_is_wellformed(over, "store_redeliver:") is False
