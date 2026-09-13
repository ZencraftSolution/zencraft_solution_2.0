from django import forms

from apps.core.forms import HoneypotMixin

from .models import Order


class CheckoutForm(HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(
        required=True,
        label="I agree to the terms of service and to Zencraft Solution storing these details to deliver my order.",
    )

    class Meta:
        model = Order
        fields = ["customer_name", "email", "phone", "company", "country", "billing_address", "pan_vat", "notes", "consent"]
        labels = {"customer_name": "Full name", "notes": "Anything we should know before we start?"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
