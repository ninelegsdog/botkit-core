"""Tests for botkit_core.payments."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from aiogram.types import Message

from botkit_core.payments import MockPaymentProvider, YooKassaPaymentProvider, create_payment_provider


@pytest.mark.asyncio
async def test_mock_create_invoice_link() -> None:
    provider = MockPaymentProvider(prefix="https://t.me/mock/")
    link = await provider.create_invoice_link(
        title="Test", description="Desc", payload="pay_123", amount=100, currency="XTR"
    )
    assert link == "https://t.me/mock/pay_123"


@pytest.mark.asyncio
async def test_mock_create_payment_alias() -> None:
    provider = MockPaymentProvider()
    link = await provider.create_payment(
        title="Test", description="Desc", payload="pay_123", amount=100, currency="XTR"
    )
    assert "pay_123" in link


@pytest.mark.asyncio
async def test_mock_verify_payment() -> None:
    provider = MockPaymentProvider()
    msg = Message.model_validate({
        "message_id": 1,
        "date": 0,
        "chat": {"id": 1, "type": "private"},
        "successful_payment": {
            "currency": "XTR",
            "total_amount": 100,
            "invoice_payload": "pay_123",
            "telegram_payment_charge_id": "ch_123",
            "provider_payment_charge_id": "prov_123",
        },
    })
    assert await provider.verify_payment(msg) is True
    assert await provider.check_payment("pay_123") is True


@pytest.mark.asyncio
@patch("yookassa.Payment.create")
async def test_yookassa_create_invoice_link(mock_create: MagicMock) -> None:
    mock_payment = MagicMock()
    mock_payment.confirmation.confirmation_url = "https://yookassa.ru/confirm/pay_123"
    mock_create.return_value = mock_payment
    provider = YooKassaPaymentProvider(shop_id="123", secret_key="test_key")
    link = await provider.create_invoice_link(
        title="Test", description="Desc", payload="pay_123", amount=100, currency="RUB"
    )
    mock_create.assert_called_once()
    assert link == "https://yookassa.ru/confirm/pay_123"


def test_create_payment_provider_factory() -> None:
    mock = create_payment_provider("mock")
    assert isinstance(mock, MockPaymentProvider)
    yk = create_payment_provider("yookassa", shop_id="123", secret_key="key")
    assert isinstance(yk, YooKassaPaymentProvider)
    with pytest.raises(ValueError):
        create_payment_provider("unknown")
