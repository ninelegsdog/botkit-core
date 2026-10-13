"""Segments of a multi-part callback payload, read by position.

Payloads that carry more than a trailing id - `"book:date:12:2026-10-14"`,
`"rem:confirm:delete:91"` - cannot be parsed by `parse_callback_int`, which expects
everything after the prefix to be a bare integer. These read one named segment and apply
the same rules: ASCII digits only, no sign, no underscore, no whitespace, and a length a
rowid cannot exceed.
"""
from __future__ import annotations

import pytest

from botkit_core.callbacks import parse_callback_int_at


@pytest.mark.parametrize(
    ("data", "prefix", "index", "expected"),
    [
        ("book:date:12:2026-10-14", "book:date:", 0, 12),
        ("rem:confirm:delete:91", "rem:confirm:delete:", 0, 91),
        ("mem:plan:7", "mem:plan:", 0, 7),
        ("a:b:3:c", "a:", 1, 3),
        ("a:9:b", "a:", 0, 9),
    ],
)
def test_reads_the_named_segment(data, prefix, index, expected):
    assert parse_callback_int_at(data, prefix, index) == expected


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "book:date:-1:x",  # sign
        "book:date: 5:x",  # leading space - int() accepts
        "book:date:1_0:x",  # underscore - int() accepts as 10
        "book:date:٥:x",  # non-ASCII digit - int() accepts
        "other:1",  # prefix mismatch
    ],
)
def test_rejects_anything_int_would_have_accepted(data):
    assert parse_callback_int_at(data, "book:date:", 0) is None


def test_rejects_index_out_of_range():
    assert parse_callback_int_at("book:date:12", "book:date:", 0) == 12
    assert parse_callback_int_at("book:date:12", "book:date:", 5) is None
    assert parse_callback_int_at("book:date", "book:date:", 0) is None


def test_rejects_an_overlong_digit_run():
    assert parse_callback_int_at("x:" + "9" * 19, "x:", 0) is None
