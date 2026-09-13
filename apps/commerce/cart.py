from decimal import Decimal

from .models import ProductizedService

VAT_RATE = Decimal("0.13")
MAX_QTY = 12


class Cart:
    """Session cart keyed by product id. Quantity means months for monthly plans."""

    def __init__(self, request):
        self.session = request.session
        self.data = self.session.setdefault("cart", {})

    def save(self):
        self.session["cart"] = self.data
        self.session.modified = True

    def add(self, product, quantity=1):
        key = str(product.pk)
        self.data[key] = min(MAX_QTY, int(self.data.get(key, 0)) + max(1, int(quantity)))
        self.save()

    def update(self, product_id, quantity):
        key = str(product_id)
        if quantity <= 0:
            self.data.pop(key, None)
        else:
            self.data[key] = min(MAX_QTY, quantity)
        self.save()

    def clear(self):
        self.session["cart"] = {}
        self.session.modified = True

    def lines(self):
        products = ProductizedService.objects.filter(pk__in=self.data.keys(), is_active=True)
        result = []
        for product in products:
            qty = int(self.data[str(product.pk)])
            result.append({"product": product, "quantity": qty, "line_total": product.price_npr * qty})
        return result

    def totals(self):
        subtotal = sum((line["line_total"] for line in self.lines()), Decimal("0"))
        vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
        return {"subtotal": subtotal, "vat": vat, "total": subtotal + vat}

    def __len__(self):
        return sum(int(q) for q in self.data.values())
