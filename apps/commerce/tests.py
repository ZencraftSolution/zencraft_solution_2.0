import base64
import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.commerce.cart import MAX_QTY, VAT_RATE
from apps.commerce.models import Order, Payment, ProductizedService
from apps.commerce.payments import GATEWAYS, get_gateway
from apps.commerce.payments.base import to_decimal_str
from apps.core.testing import make_product

ESEWA_KEY = "8gBm/:&EnhH.1/q"
NO_KEYS = {**settings.PAYMENTS, "ESEWA_SECRET_KEY": "", "KHALTI_SECRET_KEY": "", "STRIPE_SECRET_KEY": ""}
ALL_KEYS = {**settings.PAYMENTS, "ESEWA_SECRET_KEY": ESEWA_KEY, "ESEWA_PRODUCT_CODE": "EPAYTEST",
            "KHALTI_SECRET_KEY": "khalti-test", "STRIPE_SECRET_KEY": "sk_test_123"}
HTTP = "apps.commerce.payments.gateways._http_json"
CHECKOUT = {"customer_name": "Bishal Shrestha", "email": "bishal@example.com", "phone": "9811111111", "country": "Nepal", "consent": "on"}


def esewa_sign(message, key=ESEWA_KEY):
    return base64.b64encode(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest()).decode()


def esewa_callback_data(order, payment, **overrides):
    data = {
        "transaction_code": "000AWEO", "status": "COMPLETE", "total_amount": to_decimal_str(order.total_npr),
        "transaction_uuid": f"{order.reference}-{payment.pk}", "product_code": "EPAYTEST",
        "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code,signed_field_names",
    }
    data.update(overrides)
    names = data["signed_field_names"].split(",")
    data["signature"] = esewa_sign(",".join(f"{n}={data[n]}" for n in names))
    return base64.b64encode(json.dumps(data).encode()).decode()


class CommerceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.product = make_product()

    def place_order(self, client=None, qty=1):
        client = client or self.client
        client.post(reverse("commerce:cart_add", args=[self.product.pk]), {"quantity": qty})
        response = client.post(reverse("commerce:checkout"), CHECKOUT)
        order = Order.objects.latest("created_at")
        self.assertRedirects(response, reverse("commerce:payment", args=[order.reference]))
        return order


class PublicViewTests(CommerceTestCase):
    def test_pricing_store_and_product_pages(self):
        make_product(slug="bronze", name="Help Desk", tier_label="Bronze", category="helpdesk", billing="monthly", price_npr=Decimal("45000"))
        self.assertContains(self.client.get(reverse("commerce:pricing")), "Rate card")
        store = self.client.get(reverse("commerce:store"))
        self.assertContains(store, "Help desk plans")
        self.assertContains(store, "Discovery and consultation")
        detail = self.client.get(self.product.get_absolute_url())
        self.assertContains(detail, "Rs. 60,000")
        self.assertContains(detail, '"@type":"Product"')

    def test_inactive_product_is_hidden(self):
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 404)
        self.assertContains(self.client.get(reverse("commerce:store")), "being restocked")


class CartTests(CommerceTestCase):
    def cart(self):
        return self.client.session.get("cart", {})

    def test_add_update_and_remove(self):
        self.client.post(reverse("commerce:cart_add", args=[self.product.pk]), {"quantity": "abc"})
        self.assertEqual(self.cart(), {str(self.product.pk): 1})
        self.client.post(reverse("commerce:cart_add", args=[self.product.pk]), {"quantity": 50})
        self.assertEqual(self.cart()[str(self.product.pk)], MAX_QTY)
        self.client.post(reverse("commerce:cart_update"), {f"qty-{self.product.pk}": "3", "qty-bogus": "x"})
        self.assertEqual(self.cart()[str(self.product.pk)], 3)
        response = self.client.get(reverse("commerce:cart"))
        self.assertContains(response, "Rs. 1,80,000")
        self.assertContains(response, "Rs. 23,400")  # 13% VAT
        self.client.post(reverse("commerce:cart_update"), {"remove": self.product.pk})
        self.assertEqual(self.cart(), {})
        self.assertContains(self.client.get(reverse("commerce:cart")), "Your cart is empty")

    def test_cart_add_requires_post_and_active_product(self):
        self.assertEqual(self.client.get(reverse("commerce:cart_add", args=[self.product.pk])).status_code, 405)
        ProductizedService.objects.filter(pk=self.product.pk).update(is_active=False)
        self.assertEqual(self.client.post(reverse("commerce:cart_add", args=[self.product.pk])).status_code, 404)


class CheckoutTests(CommerceTestCase):
    def test_empty_cart_redirects_to_store(self):
        self.assertRedirects(self.client.get(reverse("commerce:checkout")), reverse("commerce:store"))

    def test_invalid_details_rerender(self):
        self.client.post(reverse("commerce:cart_add", args=[self.product.pk]))
        response = self.client.post(reverse("commerce:checkout"), {**CHECKOUT, "consent": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    @override_settings(PAYMENTS=NO_KEYS)
    def test_order_snapshots_totals_and_exchange_rate(self):
        from apps.core.models import SiteSettings

        rate = SiteSettings.load().exchange_rate_npr_per_usd
        order = self.place_order(qty=2)
        subtotal = Decimal("120000")
        vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
        self.assertEqual((order.subtotal_npr, order.vat_npr, order.total_npr), (subtotal, vat, subtotal + vat))
        self.assertEqual(order.exchange_rate, rate)
        self.assertEqual(order.total_usd, ((subtotal + vat) / rate).quantize(Decimal("0.01")))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(self.client.session["cart"], {})
        self.assertIn(order.reference, self.client.session["orders"])


class OrderSessionIsolationTests(CommerceTestCase):
    @override_settings(DEBUG=True, PAYMENTS=NO_KEYS)
    def test_another_session_cannot_touch_the_order(self):
        order = self.place_order()
        stranger = self.client_class()
        urls = [
            ("get", reverse("commerce:payment", args=[order.reference])),
            ("get", reverse("commerce:order_done", args=[order.reference])),
            ("post", reverse("commerce:payment_start", args=[order.reference, "fonepay"])),
            ("get", reverse("commerce:simulate", args=["fonepay", order.reference])),
            ("get", reverse("commerce:payment_callback", args=["fonepay", order.reference, "success"])),
        ]
        for method, url in urls:
            with self.subTest(url=url):
                self.assertEqual(getattr(stranger, method)(url).status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")


@override_settings(PAYMENTS=NO_KEYS)
class PaymentFlowTests(CommerceTestCase):
    @override_settings(DEBUG=True)
    def test_sandbox_payment_and_idempotent_callback(self):
        order = self.place_order()
        start = self.client.post(reverse("commerce:payment_start", args=[order.reference, "fonepay"]))
        self.assertRedirects(start, reverse("commerce:simulate", args=["fonepay", order.reference]))
        self.assertContains(self.client.get(start.url), "Approve payment")

        callback = reverse("commerce:payment_callback", args=["fonepay", order.reference, "success"])
        mail.outbox.clear()
        self.assertRedirects(self.client.get(callback), reverse("commerce:order_done", args=[order.reference]))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertEqual(len(mail.outbox), 2)  # customer + internal

        # Replaying the callback must not re-fulfil or re-send emails.
        self.assertRedirects(self.client.get(callback), reverse("commerce:order_done", args=[order.reference]))
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(Payment.objects.filter(order=order, status="success").count(), 1)
        self.assertRedirects(self.client.get(reverse("commerce:payment", args=[order.reference])), reverse("commerce:order_done", args=[order.reference]))
        self.assertEqual(self.client.post(reverse("commerce:payment_start", args=[order.reference, "fonepay"])).status_code, 404)
        self.assertContains(self.client.get(reverse("commerce:order_done", args=[order.reference])), "Payment received")

    @override_settings(DEBUG=True)
    def test_failed_outcome_marks_failed_and_allows_retry(self):
        order = self.place_order()
        self.client.post(reverse("commerce:payment_start", args=[order.reference, "fonepay"]))
        response = self.client.get(reverse("commerce:payment_callback", args=["fonepay", order.reference, "failure"]))
        self.assertRedirects(response, reverse("commerce:payment", args=[order.reference]))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "failed")
        self.assertContains(self.client.get(reverse("commerce:payment", args=[order.reference])), "did not complete")

    def test_sandbox_unavailable_without_debug(self):
        order = self.place_order()
        self.assertEqual(self.client.post(reverse("commerce:payment_start", args=[order.reference, "fonepay"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("commerce:simulate", args=["fonepay", order.reference])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("commerce:payment", args=[order.reference])), "Fonepay QR")

    def test_unknown_gateway_and_missing_payment_404(self):
        order = self.place_order()
        self.assertEqual(self.client.post(reverse("commerce:payment_start", args=[order.reference, "paypal"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("commerce:payment_callback", args=["khalti", order.reference, "success"])).status_code, 404)

    def test_bank_transfer_and_invoice_await_payment(self):
        for code in ("bank", "invoice"):
            with self.subTest(code=code):
                order = self.place_order()
                mail.outbox.clear()
                response = self.client.post(reverse("commerce:payment_start", args=[order.reference, code]))
                self.assertRedirects(response, reverse("commerce:order_done", args=[order.reference]))
                order.refresh_from_db()
                self.assertEqual((order.payment_status, order.payment_method), ("awaiting", code))
                self.assertEqual(len(mail.outbox), 2)
                self.assertContains(self.client.get(response.url), order.reference)
                # A bank transfer callback can never mark an order paid.
                self.client.get(reverse("commerce:payment_callback", args=[code, order.reference, "success"]))
                order.refresh_from_db()
                self.assertNotEqual(order.payment_status, "paid")

    @override_settings(PAYMENTS=ALL_KEYS)
    def test_esewa_start_renders_signed_form(self):
        order = self.place_order()
        response = self.client.post(reverse("commerce:payment_start", args=[order.reference, "esewa"]))
        self.assertTemplateUsed(response, "commerce/gateway_redirect.html")
        fields = response.context["result"].fields
        payment = order.payments.get()
        message = f"total_amount={fields['total_amount']},transaction_uuid={order.reference}-{payment.pk},product_code=EPAYTEST"
        self.assertEqual(fields["signature"], esewa_sign(message))
        self.assertNotIn("?", fields["success_url"])  # eSewa appends its own ?data=

    @override_settings(PAYMENTS=ALL_KEYS)
    def test_khalti_and_stripe_start_redirect_to_provider(self):
        order = self.place_order()
        with mock.patch(HTTP, return_value={"pidx": "PIDX123", "payment_url": "https://pay.khalti.com/x"}) as http:
            response = self.client.post(reverse("commerce:payment_start", args=[order.reference, "khalti"]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://pay.khalti.com/x")
        self.assertEqual(http.call_args.args[1]["amount"], int(order.total_npr * 100))
        self.assertEqual(order.payments.get(gateway="khalti").transaction_id, "PIDX123")

        with mock.patch(HTTP, return_value={"id": "cs_test_1", "url": "https://checkout.stripe.com/c/cs_test_1"}) as http:
            response = self.client.post(reverse("commerce:payment_start", args=[order.reference, "stripe"]))
        self.assertEqual(response.url, "https://checkout.stripe.com/c/cs_test_1")
        form = http.call_args.args[1]
        self.assertEqual(form["line_items[0][price_data][unit_amount]"], int(order.total_usd * 100))
        self.assertEqual(form["line_items[0][price_data][currency]"], "usd")

    @override_settings(PAYMENTS=ALL_KEYS)
    def test_provider_outage_shows_message(self):
        order = self.place_order()
        for code in ("khalti", "stripe"):
            with self.subTest(code=code), mock.patch(HTTP, side_effect=OSError("timeout")):
                response = self.client.post(reverse("commerce:payment_start", args=[order.reference, code]))
                self.assertRedirects(response, reverse("commerce:payment", args=[order.reference]), fetch_redirect_response=False)

    @override_settings(PAYMENTS=ALL_KEYS)
    def test_esewa_full_callback_marks_paid(self):
        order = self.place_order()
        self.client.post(reverse("commerce:payment_start", args=[order.reference, "esewa"]))
        payment = order.payments.get()
        url = reverse("commerce:payment_callback", args=["esewa", order.reference, "success"])
        response = self.client.get(url, {"data": esewa_callback_data(order, payment)})
        self.assertRedirects(response, reverse("commerce:order_done", args=[order.reference]))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.transaction_id), ("success", "000AWEO"))


class GatewayRegistryTests(TestCase):
    def test_registry(self):
        self.assertEqual(set(GATEWAYS), {"esewa", "khalti", "fonepay", "stripe", "bank", "invoice"})
        self.assertIsNone(get_gateway("nope"))
        self.assertEqual(get_gateway("stripe").currency, "USD")

    @override_settings(DEBUG=False, PAYMENTS=NO_KEYS)
    def test_unconfigured_gateways_unavailable_in_production(self):
        available = {code for code, g in GATEWAYS.items() if g.is_available()}
        self.assertEqual(available, {"bank", "invoice"})


@override_settings(PAYMENTS=ALL_KEYS)
class GatewayVerifyTests(TestCase):
    """Success path plus rejection of forged or mismatched provider data for every gateway (item 7)."""

    def setUp(self):
        self.factory = RequestFactory()
        self.order = Order.objects.create(
            reference="ZC-VERIFY", customer_name="A", email="a@example.com", phone="1", subtotal_npr=Decimal("60000"),
            vat_npr=Decimal("7800"), total_npr=Decimal("67800"), exchange_rate=Decimal("134.25"), total_usd=Decimal("505.03"),
        )

    def payment(self, gateway, transaction_id=""):
        return Payment.objects.create(order=self.order, gateway=gateway, amount=self.order.total_npr, transaction_id=transaction_id)

    def request(self, **params):
        return self.factory.get("/callback/", params)

    # eSewa -----------------------------------------------------------------
    def test_esewa_valid(self):
        p = self.payment("esewa")
        result = get_gateway("esewa").verify(self.order, p, self.request(data=esewa_callback_data(self.order, p)))
        self.assertTrue(result.success)

    def test_esewa_forged_signature_rejected(self):
        p = self.payment("esewa")
        payload = json.loads(base64.b64decode(esewa_callback_data(self.order, p)))
        payload["signature"] = esewa_sign("total_amount=1.00", key="attacker-key")
        forged = base64.b64encode(json.dumps(payload).encode()).decode()
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=forged)).success)

    def test_esewa_tampered_field_after_signing_rejected(self):
        p = self.payment("esewa")
        payload = json.loads(base64.b64decode(esewa_callback_data(self.order, p)))
        payload["status"] = "COMPLETE"
        payload["total_amount"] = "1.00"  # changed without re-signing
        tampered = base64.b64encode(json.dumps(payload).encode()).decode()
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=tampered)).success)

    def test_esewa_mismatched_transaction_uuid_rejected(self):
        p = self.payment("esewa")
        data = esewa_callback_data(self.order, p, transaction_uuid="ZC-OTHER-1")
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=data)).success)

    def test_esewa_validly_signed_wrong_amount_rejected(self):
        p = self.payment("esewa")
        data = esewa_callback_data(self.order, p, total_amount="10.00")
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=data)).success)

    def test_esewa_incomplete_status_missing_and_garbage_data_rejected(self):
        p = self.payment("esewa")
        gw = get_gateway("esewa")
        self.assertFalse(gw.verify(self.order, p, self.request(data=esewa_callback_data(self.order, p, status="PENDING"))).success)
        self.assertFalse(gw.verify(self.order, p, self.request()).success)
        self.assertFalse(gw.verify(self.order, p, self.request(data="%%%not-base64")).success)
        self.assertFalse(gw.verify(self.order, p, self.request(data=esewa_callback_data(self.order, p)), outcome="failure").success)

    # Khalti ----------------------------------------------------------------
    def khalti_lookup(self, **overrides):
        data = {"pidx": "PIDX1", "status": "Completed", "total_amount": int(self.order.total_npr * 100), "transaction_id": "KT-9"}
        data.update(overrides)
        return data

    def test_khalti_valid(self):
        p = self.payment("khalti", "PIDX1")
        with mock.patch(HTTP, return_value=self.khalti_lookup()) as http:
            result = get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX1"))
        self.assertTrue(result.success)
        self.assertEqual(result.transaction_id, "KT-9")
        self.assertTrue(http.call_args.args[0].endswith("epayment/lookup/"))

    def test_khalti_mismatched_pidx_rejected_without_calling_provider(self):
        p = self.payment("khalti", "PIDX1")
        with mock.patch(HTTP) as http:
            self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX-ATTACKER")).success)
            self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request()).success)
        http.assert_not_called()

    def test_khalti_mismatched_amount_rejected(self):
        p = self.payment("khalti", "PIDX1")
        with mock.patch(HTTP, return_value=self.khalti_lookup(total_amount=1000)):
            self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX1")).success)

    def test_khalti_lookup_pidx_mismatch_rejected(self):
        p = self.payment("khalti", "PIDX1")
        with mock.patch(HTTP, return_value=self.khalti_lookup(pidx="PIDX-OTHER")):
            self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX1")).success)

    def test_khalti_incomplete_status_rejected(self):
        p = self.payment("khalti", "PIDX1")
        for status in ("Pending", "Refunded", "Expired", "User canceled"):
            with self.subTest(status=status), mock.patch(HTTP, return_value=self.khalti_lookup(status=status)):
                self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX1")).success)

    def test_khalti_provider_error_rejected(self):
        p = self.payment("khalti", "PIDX1")
        with mock.patch(HTTP, side_effect=OSError("down")):
            self.assertFalse(get_gateway("khalti").verify(self.order, p, self.request(pidx="PIDX1")).success)

    # Stripe ----------------------------------------------------------------
    def stripe_session(self, **overrides):
        data = {"id": "cs_1", "payment_status": "paid", "payment_intent": "pi_1", "amount_total": int(self.order.total_usd * 100),
                "currency": "usd", "client_reference_id": f"{self.order.reference}-{{pk}}"}
        data.update(overrides)
        return data

    def stripe_payment(self):
        p = self.payment("stripe", "cs_1")
        p.currency = "USD"
        p.save()
        return p

    def with_ref(self, p, **overrides):
        data = self.stripe_session(**overrides)
        data["client_reference_id"] = data["client_reference_id"].replace("{pk}", str(p.pk))
        return data

    def test_stripe_valid(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, return_value=self.with_ref(p)):
            result = get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1"))
        self.assertTrue(result.success)
        self.assertEqual(result.transaction_id, "pi_1")

    def test_stripe_mismatched_session_rejected_without_calling_provider(self):
        p = self.stripe_payment()
        with mock.patch(HTTP) as http:
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_attacker")).success)
        http.assert_not_called()

    def test_stripe_unpaid_rejected(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, return_value=self.with_ref(p, payment_status="unpaid")):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)

    def test_stripe_mismatched_amount_rejected(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, return_value=self.with_ref(p, amount_total=100)):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)

    def test_stripe_mismatched_currency_rejected(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, return_value=self.with_ref(p, currency="inr")):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)

    def test_stripe_mismatched_reference_or_session_id_rejected(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, return_value=self.with_ref(p, client_reference_id="ZC-OTHER-1")):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)
        with mock.patch(HTTP, return_value=self.with_ref(p, id="cs_other")):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)

    def test_stripe_provider_error_rejected(self):
        p = self.stripe_payment()
        with mock.patch(HTTP, side_effect=OSError("down")):
            self.assertFalse(get_gateway("stripe").verify(self.order, p, self.request(session_id="cs_1")).success)

    # Sandbox / unconfigured ---------------------------------------------------
    @override_settings(DEBUG=True, PAYMENTS=NO_KEYS)
    def test_sandbox_requires_matching_session_marker(self):
        p = self.payment("fonepay")
        request = self.request()
        request.session = {"simulated_payment": p.pk + 1}
        self.assertFalse(get_gateway("fonepay").verify(self.order, p, request).success)
        request.session = {"simulated_payment": p.pk}
        self.assertTrue(get_gateway("fonepay").verify(self.order, p, request).success)

    @override_settings(DEBUG=False, PAYMENTS=NO_KEYS)
    def test_unconfigured_gateway_never_verifies_in_production(self):
        p = self.payment("fonepay")
        request = self.request()
        request.session = {"simulated_payment": p.pk}
        self.assertFalse(get_gateway("fonepay").verify(self.order, p, request).success)
        for code in ("esewa", "khalti", "stripe"):
            with self.subTest(code=code):
                self.assertFalse(get_gateway(code).verify(self.order, self.payment(code), request).success)

    def test_esewa_fields_outside_signature_rejected(self):
        p = self.payment("esewa")
        # Signed correctly, but status and amount are not covered by the signature.
        data = esewa_callback_data(self.order, p, signed_field_names="transaction_uuid,product_code")
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=data)).success)

    def test_esewa_wrong_product_code_rejected(self):
        p = self.payment("esewa")
        data = esewa_callback_data(self.order, p, product_code="OTHER-MERCHANT")
        self.assertFalse(get_gateway("esewa").verify(self.order, p, self.request(data=data)).success)
