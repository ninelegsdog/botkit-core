"""Unified payment providers for BotKit.

Supports YooKassa, Telegram Stars (XTR), and Mock for testing.
Unified Protocol covers both create_invoice_link/verify_payment (bookingbot)
and create_payment/check_payment (delivery etc.) via aliases.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from aiogram.types import Message

STARS_CURRENCY = "XTR"


@runtime_checkable
class PaymentProvider(Protocol):
    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str: ...

    async def verify_payment(self, message: Message) -> bool: ...

    # Aliases for delivery-style API
    async def create_payment(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str: ...

    async def check_payment(self, payment_id: str) -> bool: ...


class MockPaymentProvider:
    def __init__(self, *, prefix: str = "https://t.me/mock-bot/invoice/") -> None:
        self._prefix = prefix

    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str:
        return f"{self._prefix}{payload}"

    async def create_payment(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str:
        return await self.create_invoice_link(
            title=title, description=description, payload=payload, amount=amount, currency=currency
        )

    async def verify_payment(self, message: Message) -> bool:
        payment = message.successful_payment
        return bool(payment is not None and payment.total_amount > 0)

    async def check_payment(self, payment_id: str) -> bool:
        return True


class YooKassaPaymentProvider:
    def __init__(self, shop_id: str, secret_key: str) -> None:
        from yookassa import Configuration

        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "RUB"
    ) -> str:
        from yookassa import Payment

        payment = Payment.create(
            {
                "amount": {"value": f"{amount}.00", "currency": currency},
                "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
                "capture": True,
                "description": description,
                "metadata": {"payload": payload},
            }
        )
        return str(payment.confirmation.confirmation_url)

    async def create_payment(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "RUB"
    ) -> str:
        return await self.create_invoice_link(
            title=title, description=description, payload=payload, amount=amount, currency=currency
        )

    async def verify_payment(self, message: Message) -> bool:
        payment = message.successful_payment
        return bool(payment is not None and payment.total_amount > 0)

    async def check_payment(self, payment_id: str) -> bool:
        return bool(payment_id)


def create_payment_provider(name: str, **kwargs: str) -> PaymentProvider:
    if name == "mock":
        return MockPaymentProvider(prefix=kwargs.get("prefix", "https://t.me/mock-bot/invoice/"))
    if name == "yookassa":
        return YooKassaPaymentProvider(kwargs["shop_id"], kwargs["secret_key"])
    raise ValueError(f"Unknown payment provider: {name}")


def attach_payment_handlers(router, provider: PaymentProvider, *, on_confirmed=None) -> None:
    from aiogram import F
    from aiogram.types import Message, PreCheckoutQuery

    @router.pre_checkout_query()
    async def approve_pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def confirm_payment(message: Message) -> None:
        payment = message.successful_payment
        if payment is None:
            return
        payload = payment.invoice_payload
        if on_confirmed is not None:
            await on_confirmed(payload)

