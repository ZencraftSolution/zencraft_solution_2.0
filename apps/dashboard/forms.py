from django import forms
from django.contrib.auth import get_user_model

from apps.careers.models import JobApplication
from apps.commerce.models import Order
from apps.core.models import SiteSettings
from apps.estimator.models import EstimatorConfig, ProjectInquiry


class LeadUpdateForm(forms.ModelForm):
    class Meta:
        model = ProjectInquiry
        fields = ["status", "assigned_to", "internal_notes"]
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(is_staff=True, is_active=True)


class NoteForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Add a note", max_length=4000)


class ApplicationUpdateForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[("", "Not rated")] + [(i, f"{i} / 5") for i in range(1, 6)], coerce=int, empty_value=None, required=False,
    )

    class Meta:
        model = JobApplication
        fields = ["status", "rating"]


class OrderUpdateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["payment_status", "fulfilment_status"]


class EstimatorConfigForm(forms.ModelForm):
    class Meta:
        model = EstimatorConfig
        # Explicit list: a new model field must be deliberately exposed, never editable by accident.
        fields = [
            "blended_hourly_rate_npr", "contingency_pct", "range_low_factor", "range_high_factor", "team_hours_per_week",
            "minimum_project_npr", "design_multipliers", "urgency_multipliers", "team_multipliers", "platform_coefficients",
            "disclaimer",
        ]
        widgets = {
            "design_multipliers": forms.Textarea(attrs={"rows": 4, "class": "is-code"}),
            "urgency_multipliers": forms.Textarea(attrs={"rows": 5, "class": "is-code"}),
            "team_multipliers": forms.Textarea(attrs={"rows": 4, "class": "is-code"}),
            "platform_coefficients": forms.Textarea(attrs={"rows": 7, "class": "is-code"}),
            "disclaimer": forms.Textarea(attrs={"rows": 3}),
        }

    def _validate_map(self, name, keys):
        value = self.cleaned_data.get(name)
        if not isinstance(value, dict):
            raise forms.ValidationError("Enter a JSON object, for example {\"key\": 1.0}.")
        for key in keys:
            if key not in value:
                raise forms.ValidationError(f"Missing key: {key}")
        try:
            return {k: float(v) for k, v in value.items()}
        except (TypeError, ValueError):
            raise forms.ValidationError("All values must be numbers.") from None

    def clean_design_multipliers(self):
        return self._validate_map("design_multipliers", ["existing", "uiux", "branding"])

    def clean_urgency_multipliers(self):
        return self._validate_map("urgency_multipliers", ["flexible", "standard", "fast", "critical"])

    def clean_team_multipliers(self):
        return self._validate_map("team_multipliers", ["fixed", "dedicated", "unsure"])

    def clean_platform_coefficients(self):
        return self._validate_map("platform_coefficients", ["web", "ios", "android", "windows", "macos", "linux"])


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "company_name", "tagline", "email", "careers_email", "phone", "whatsapp", "address", "office_hours",
            "linkedin_url", "github_url", "facebook_url", "x_url", "exchange_rate_npr_per_usd", "hero_title", "hero_subtitle",
            "stat_projects", "stat_clients", "stat_engineers", "stat_uptime", "stat_years",
        ]
