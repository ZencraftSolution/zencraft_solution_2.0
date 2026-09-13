from django import forms
from django.utils import timezone

from .models import ConsultationBooking, ContactSubmission, NewsletterSubscriber


class HoneypotMixin(forms.Form):
    """Bots fill every field. Humans never see this one."""

    website = forms.CharField(required=False, label="Leave this field empty", widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam check failed.")
        return ""


class ContactForm(HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(
        required=True,
        label="I agree that Zencraft Solution may store these details to reply to my message, as described in the privacy policy.",
    )

    class Meta:
        model = ContactSubmission
        fields = ["name", "email", "phone", "company", "subject", "message", "consent"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}


class ConsultationForm(HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(required=True, label="I agree to be contacted about this consultation, as described in the privacy policy.")

    class Meta:
        model = ConsultationBooking
        fields = ["name", "company", "email", "phone", "topic", "preferred_date", "preferred_slot", "message", "consent"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {"message": "Anything we should read before the call?"}

    def clean_preferred_date(self):
        date = self.cleaned_data["preferred_date"]
        if date < timezone.localdate():
            raise forms.ValidationError("Please pick today or a future date.")
        if date.weekday() == 5:
            raise forms.ValidationError("Our office is closed on Saturdays. Please choose another day.")
        return date


class NewsletterForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email"]

    def validate_unique(self):
        # Re-subscribing an existing address is handled in the view, not as an error.
        pass
