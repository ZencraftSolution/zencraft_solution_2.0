from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.urls import reverse


@dataclass
class GatewayResult:
    kind: str  # "redirect", "form", "instructions" or "simulate"
    url: str = ""
    fields: dict = field(default_factory=dict)
    message: str = ""


@dataclass
class VerifyResult:
    success: bool
    transaction_id: str = ""
    raw: dict = field(default_factory=dict)


class PaymentGateway:
    code = ""
    label = ""
    currency = "NPR"
    description = ""
    icon = "credit-card"

    def is_configured(self):
        return False

    def is_available(self):
        return self.is_configured() or settings.DEBUG

    def amount_for(self, order):
        return order.total_usd if self.currency == "USD" else order.total_npr

    def callback_url(self, request, order, outcome="success"):
        return request.build_absolute_uri(reverse("commerce:payment_callback", args=[self.code, order.reference, outcome]))

    def initiate(self, order, payment, request):
        """Return a GatewayResult telling the view how to hand the customer over."""
        if not self.is_configured():
            return GatewayResult(kind="simulate", url=reverse("commerce:simulate", args=[self.code, order.reference]))
        raise NotImplementedError

    def verify(self, order, payment, request, outcome="success"):
        """Confirm a payment on callback. Never trust query parameters without checking with the provider."""
        if outcome != "success":
            return VerifyResult(success=False, raw={"outcome": outcome})
        if not self.is_configured() and settings.DEBUG:
            ok = request.session.get("simulated_payment") == payment.pk
            return VerifyResult(success=ok, transaction_id=f"SIM-{payment.pk}", raw={"simulated": True})
        raise NotImplementedError


def to_decimal_str(amount):
    return str(Decimal(amount).quantize(Decimal("0.01")))
