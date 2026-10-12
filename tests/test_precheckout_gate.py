"""pre_checkout is the only gate between the user and the charge.

`pre_checkout_query` is where a bot approves or refuses a payment. Answering `ok=True`
without looking at anything approves whatever amount the client sends, so a hand-crafted
update buys a 10-Star product for 1 Star. The original handler did exactly that.
"""
from __future__ import annotations

import pytest

from botkit_core.payments import attach_payment_handlers


class FakeQuery:
    """Stands in for aiogram's PreCheckoutQuery - only what the handler touches."""

    def __init__(self, invoice_payload: str = "pack_10", total_amount: int = 10) -> None:
        self.invoice_payload = invoice_payload
        self.total_amount = total_amount
        self.answers: list[dict] = []

    async def answer(self, ok: bool, **kwargs: object) -> None:
        self.answers.append({"ok": ok, **kwargs})


def _router_for(**kwargs):
    """Minimal router stub that captures whatever the helper registers."""
    import aiogram

    router = aiogram.Router()
    attach_payment_handlers(router, provider=None, **kwargs)
    pre = list(router.pre_checkout_query.handlers)
    assert pre, "no pre_checkout_query handler was registered"
    return pre[0].callback


@pytest.mark.asyncio
async def test_accepts_the_declared_product():
    handler = _router_for(expected_payloads={"pack_10"}, expected_amount=10)
    query = FakeQuery("pack_10", 10)
    await handler(query)
    assert query.answers[0]["ok"] is True


@pytest.mark.asyncio
async def test_rejects_a_forged_amount():
    """The vulnerability: same product, one Star instead of ten."""
    handler = _router_for(expected_payloads={"pack_10"}, expected_amount=10)
    query = FakeQuery("pack_10", 1)
    await handler(query)
    assert query.answers[0]["ok"] is False


@pytest.mark.asyncio
async def test_rejects_an_unknown_payload():
    handler = _router_for(expected_payloads={"pack_10"}, expected_amount=10)
    query = FakeQuery("pack_free", 0)
    await handler(query)
    assert query.answers[0]["ok"] is False


@pytest.mark.asyncio
async def test_fails_closed_when_nothing_was_declared():
    """A bot that forgot to declare its products must not approve a charge.

    Approving a payment nobody described is the failure mode itself, so the default is
    refusal rather than `ok=True`.
    """
    handler = _router_for()
    query = FakeQuery("whatever", 1)
    await handler(query)
    assert query.answers[0]["ok"] is False


@pytest.mark.asyncio
async def test_payload_only_check_still_catches_amount_confusion():
    """With only payloads declared the amount is not second-guessed."""
    handler = _router_for(expected_payloads={"pack_10"})
    query = FakeQuery("pack_10", 999)
    await handler(query)
    assert query.answers[0]["ok"] is True
