import base64
import hashlib
import hmac
import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings

from .base import GatewayResult, PaymentGateway, VerifyResult, to_decimal_str

logger = logging.getLogger(__name__)
CFG = settings.PAYMENTS


def _http_json(url, data=None, headers=None, form=False, method="POST"):
    headers = dict(headers or {})
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = json.dumps(data).encode()
            headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


class EsewaGateway(PaymentGateway):
    code = "esewa"
    label = "eSewa"
    icon = "wallet"
    description = "Pay from your eSewa wallet in NPR."

    def is_configured(self):
        return bool(CFG["ESEWA_SECRET_KEY"] and CFG["ESEWA_PRODUCT_CODE"])

    def _sign(self, message):
        digest = hmac.new(CFG["ESEWA_SECRET_KEY"].encode(), message.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def initiate(self, order, payment, request):
        if not self.is_configured():
            return super().initiate(order, payment, request)
        total = to_decimal_str(order.total_npr)
        uuid = f"{order.reference}-{payment.pk}"
        fields = {
            "amount": total,
            "tax_amount": "0",
            "total_amount": total,
            "transaction_uuid": uuid,
            "product_code": CFG["ESEWA_PRODUCT_CODE"],
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": self.callback_url(request, order, "success"),
            "failure_url": self.callback_url(request, order, "failure"),
            "signed_field_names": "total_amount,transaction_uuid,product_code",
        }
        fields["signature"] = self._sign(f"total_amount={total},transaction_uuid={uuid},product_code={CFG['ESEWA_PRODUCT_CODE']}")
        return GatewayResult(kind="form", url=CFG["ESEWA_FORM_URL"], fields=fields)

    def verify(self, order, payment, request, outcome="success"):
        if outcome != "success" or not self.is_configured():
            return super().verify(order, payment, request, outcome)
        encoded = request.GET.get("data")
        if not encoded:
            return VerifyResult(success=False, raw={"error": "missing data"})
        try:
            data = json.loads(base64.b64decode(encoded).decode())
        except (ValueError, json.JSONDecodeError):
            return VerifyResult(success=False, raw={"error": "undecodable"})
        names = data.get("signed_field_names", "").split(",")
        message = ",".join(f"{n}={data.get(n, '')}" for n in names)
        signature_ok = hmac.compare_digest(self._sign(message), data.get("signature", ""))
        uuid_ok = data.get("transaction_uuid") == f"{order.reference}-{payment.pk}"
        success = signature_ok and uuid_ok and data.get("status") == "COMPLETE"
        return VerifyResult(success=success, transaction_id=data.get("transaction_code", ""), raw=data)


class KhaltiGateway(PaymentGateway):
    code = "khalti"
    label = "Khalti"
    icon = "device-mobile"
    description = "Pay with Khalti wallet, mobile banking or cards."

    def is_configured(self):
        return bool(CFG["KHALTI_SECRET_KEY"])

    def _headers(self):
        return {"Authorization": f"Key {CFG['KHALTI_SECRET_KEY']}"}

    def initiate(self, order, payment, request):
        if not self.is_configured():
            return super().initiate(order, payment, request)
        payload = {
            "return_url": self.callback_url(request, order, "success"),
            "website_url": request.build_absolute_uri("/"),
            "amount": int(order.total_npr * 100),
            "purchase_order_id": f"{order.reference}-{payment.pk}",
            "purchase_order_name": f"Zencraft order {order.reference}",
            "customer_info": {"name": order.customer_name, "email": order.email, "phone": order.phone},
        }
        try:
            data = _http_json(CFG["KHALTI_API_URL"] + "epayment/initiate/", payload, self._headers())
        except Exception as exc:  # network or provider error
            logger.exception("Khalti initiate failed")
            return GatewayResult(kind="instructions", message=f"Khalti is unavailable right now ({exc.__class__.__name__}). Please try another method.")
        payment.transaction_id = data.get("pidx", "")
        payment.raw_response = data
        payment.save(update_fields=["transaction_id", "raw_response"])
        return GatewayResult(kind="redirect", url=data["payment_url"])

    def verify(self, order, payment, request, outcome="success"):
        if outcome != "success" or not self.is_configured():
            return super().verify(order, payment, request, outcome)
        pidx = request.GET.get("pidx", "")
        if not pidx or pidx != payment.transaction_id:
            return VerifyResult(success=False, raw={"error": "pidx mismatch"})
        data = _http_json(CFG["KHALTI_API_URL"] + "epayment/lookup/", {"pidx": pidx}, self._headers())
        ok = data.get("status") == "Completed" and int(data.get("total_amount", 0)) == int(order.total_npr * 100)
        return VerifyResult(success=ok, transaction_id=data.get("transaction_id", pidx), raw=data)


class FonepayGateway(PaymentGateway):
    code = "fonepay"
    label = "Fonepay QR"
    icon = "qr-code"
    description = "Scan with any Nepali mobile banking app."
    # Fonepay dynamic QR requires merchant credentials issued by the bank. Until they are
    # configured this gateway runs through the sandbox simulator in DEBUG only.


class StripeGateway(PaymentGateway):
    code = "stripe"
    label = "Card payment"
    currency = "USD"
    icon = "credit-card"
    description = "International Visa, Mastercard or Amex, charged in USD."

    def is_configured(self):
        return bool(CFG["STRIPE_SECRET_KEY"])

    def _headers(self):
        return {"Authorization": f"Bearer {CFG['STRIPE_SECRET_KEY']}"}

    def initiate(self, order, payment, request):
        if not self.is_configured():
            return super().initiate(order, payment, request)
        success = self.callback_url(request, order, "success") + "?session_id={CHECKOUT_SESSION_ID}"
        form = {
            "mode": "payment",
            "success_url": success,
            "cancel_url": self.callback_url(request, order, "failure"),
            "client_reference_id": f"{order.reference}-{payment.pk}",
            "customer_email": order.email,
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": int(order.total_usd * 100),
            "line_items[0][price_data][product_data][name]": f"Zencraft Solution order {order.reference}",
        }
        try:
            data = _http_json("https://api.stripe.com/v1/checkout/sessions", form, self._headers(), form=True)
        except Exception as exc:
            logger.exception("Stripe initiate failed")
            return GatewayResult(kind="instructions", message=f"Card payments are unavailable right now ({exc.__class__.__name__}).")
        payment.transaction_id = data["id"]
        payment.save(update_fields=["transaction_id"])
        return GatewayResult(kind="redirect", url=data["url"])

    def verify(self, order, payment, request, outcome="success"):
        if outcome != "success" or not self.is_configured():
            return super().verify(order, payment, request, outcome)
        session_id = request.GET.get("session_id", "")
        if session_id != payment.transaction_id:
            return VerifyResult(success=False, raw={"error": "session mismatch"})
        data = _http_json(f"https://api.stripe.com/v1/checkout/sessions/{session_id}", headers=self._headers(), method="GET")
        return VerifyResult(success=data.get("payment_status") == "paid", transaction_id=data.get("payment_intent") or session_id, raw={"id": data.get("id"), "payment_status": data.get("payment_status")})


class BankTransferGateway(PaymentGateway):
    code = "bank"
    label = "Bank transfer"
    icon = "bank"
    description = "Transfer to our NPR or USD account. We confirm within one working day."

    def is_configured(self):
        return True

    def initiate(self, order, payment, request):
        return GatewayResult(kind="instructions", message="bank")

    def verify(self, order, payment, request, outcome="success"):
        return VerifyResult(success=False)


class InvoiceGateway(BankTransferGateway):
    code = "invoice"
    label = "Invoice"
    icon = "receipt"
    description = "For companies that need a PAN/VAT invoice with 15-day terms."

    def initiate(self, order, payment, request):
        return GatewayResult(kind="instructions", message="invoice")


GATEWAYS = {g.code: g for g in [EsewaGateway(), KhaltiGateway(), FonepayGateway(), StripeGateway(), BankTransferGateway(), InvoiceGateway()]}


def get_gateway(code):
    return GATEWAYS.get(code)
