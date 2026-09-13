from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.core.models import SiteSettings
from apps.core.utils import make_reference, rate_limit

from .cart import Cart
from .forms import CheckoutForm
from .models import EngagementModel, FixedPriceRange, Order, OrderItem, Payment, ProductizedService, RoleRate
from .payments import GATEWAYS, get_gateway


def pricing(request):
    return render(request, "commerce/pricing.html", {
        "engagement_models": EngagementModel.objects.all(),
        "role_rates": RoleRate.objects.all(),
        "ranges": FixedPriceRange.objects.all(),
        "featured_products": ProductizedService.objects.filter(is_active=True, featured=True)[:3],
    })


def store(request):
    products = ProductizedService.objects.filter(is_active=True)
    groups = []
    for code, label in ProductizedService.CATEGORY_CHOICES:
        items = [p for p in products if p.category == code]
        if items:
            groups.append({"code": code, "label": label, "items": items})
    return render(request, "commerce/store.html", {"groups": groups})


def product_detail(request, slug):
    product = get_object_or_404(ProductizedService, slug=slug, is_active=True)
    siblings = ProductizedService.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)
    return render(request, "commerce/product_detail.html", {"product": product, "siblings": siblings})


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(ProductizedService, pk=pk, is_active=True)
    try:
        qty = int(request.POST.get("quantity", 1))
    except ValueError:
        qty = 1
    Cart(request).add(product, qty)
    messages.success(request, f"{product} was added to your cart.")
    return redirect("commerce:cart")


@require_POST
def cart_update(request):
    cart = Cart(request)
    for key, value in request.POST.items():
        if key.startswith("qty-"):
            try:
                cart.update(int(key[4:]), int(value))
            except ValueError:
                continue
    if "remove" in request.POST:
        cart.update(int(request.POST["remove"]), 0)
    return redirect("commerce:cart")


def cart_detail(request):
    cart = Cart(request)
    return render(request, "commerce/cart.html", {"lines": cart.lines(), "totals": cart.totals()})


@rate_limit("checkout", limit=8, window=900)
def checkout(request):
    cart = Cart(request)
    lines = cart.lines()
    if not lines:
        messages.info(request, "Your cart is empty.")
        return redirect("commerce:store")
    totals = cart.totals()
    form = CheckoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        rate = SiteSettings.load().exchange_rate_npr_per_usd
        with transaction.atomic():
            order = form.save(commit=False)
            order.reference = make_reference("ZC")
            order.subtotal_npr = totals["subtotal"]
            order.vat_npr = totals["vat"]
            order.total_npr = totals["total"]
            order.exchange_rate = rate
            order.total_usd = (totals["total"] / rate).quantize(Decimal("0.01"))
            order.save()
            for line in lines:
                product = line["product"]
                OrderItem.objects.create(
                    order=order, product=product, name=str(product), billing=product.billing,
                    unit_price_npr=product.price_npr, quantity=line["quantity"], line_total_npr=line["line_total"],
                )
        request.session.setdefault("orders", []).append(order.reference)
        request.session.modified = True
        cart.clear()
        return redirect("commerce:payment", reference=order.reference)
    return render(request, "commerce/checkout.html", {"form": form, "lines": lines, "totals": totals})


def _session_order(request, reference):
    if reference not in request.session.get("orders", []):
        raise Http404
    return get_object_or_404(Order.objects.prefetch_related("items"), reference=reference)


def payment_select(request, reference):
    order = _session_order(request, reference)
    if order.payment_status == "paid":
        return redirect("commerce:order_done", reference=reference)
    gateways = [g for g in GATEWAYS.values() if g.is_available()]
    return render(request, "commerce/payment.html", {"order": order, "gateways": gateways, "debug": settings.DEBUG})


@require_POST
def payment_start(request, reference, gateway):
    order = _session_order(request, reference)
    gw = get_gateway(gateway)
    if gw is None or not gw.is_available() or order.payment_status == "paid":
        raise Http404
    payment = Payment.objects.create(order=order, gateway=gw.code, amount=gw.amount_for(order), currency=gw.currency)
    order.payment_method = gw.code
    order.save(update_fields=["payment_method", "updated_at"])
    result = gw.initiate(order, payment, request)

    if result.kind == "redirect":
        return redirect(result.url)
    if result.kind == "form":
        return render(request, "commerce/gateway_redirect.html", {"result": result, "gateway": gw})
    if result.kind == "simulate":
        request.session["simulated_payment"] = payment.pk
        return redirect(result.url)
    if result.message in ("bank", "invoice"):
        order.payment_status = "awaiting"
        order.save(update_fields=["payment_status", "updated_at"])
        _send_order_emails(order)
        return redirect("commerce:order_done", reference=reference)
    messages.error(request, result.message)
    return redirect("commerce:payment", reference=reference)


def simulate(request, gateway, reference):
    if not settings.DEBUG:
        raise Http404
    order = _session_order(request, reference)
    gw = get_gateway(gateway)
    if gw is None:
        raise Http404
    return render(request, "commerce/simulate.html", {"order": order, "gateway": gw})


def payment_callback(request, gateway, reference, outcome):
    order = _session_order(request, reference)
    gw = get_gateway(gateway)
    payment = order.payments.filter(gateway=gateway).first()
    if gw is None or payment is None:
        raise Http404
    if order.payment_status == "paid":
        return redirect("commerce:order_done", reference=reference)
    result = gw.verify(order, payment, request, outcome)
    payment.raw_response = result.raw
    if result.success:
        payment.status = "success"
        payment.transaction_id = result.transaction_id or payment.transaction_id
        order.payment_status = "paid"
        order.save(update_fields=["payment_status", "updated_at"])
        payment.save()
        request.session.pop("simulated_payment", None)
        _send_order_emails(order)
        return redirect("commerce:order_done", reference=reference)
    payment.status = "failed"
    payment.save()
    order.payment_status = "failed"
    order.save(update_fields=["payment_status", "updated_at"])
    messages.error(request, "The payment was not completed. You have not been charged. Please try again or choose another method.")
    return redirect("commerce:payment", reference=reference)


def order_done(request, reference):
    order = _session_order(request, reference)
    return render(request, "commerce/order_done.html", {"order": order})


def _send_order_emails(order):
    body = render_to_string("emails/order_ack.txt", {"order": order})
    send_mail(f"Your Zencraft order {order.reference}", body, settings.DEFAULT_FROM_EMAIL, [order.email], fail_silently=True)
    send_mail(f"New order {order.reference} ({order.get_payment_status_display()})", body, settings.DEFAULT_FROM_EMAIL, [settings.INTERNAL_NOTIFY_EMAIL], fail_silently=True)
