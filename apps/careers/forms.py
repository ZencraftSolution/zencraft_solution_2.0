from datetime import timedelta

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.core.forms import HoneypotMixin
from apps.core.uploads import validate_document

from .models import EducationEntry, ExperienceEntry, JobApplication, ProjectEntry


class JobApplicationForm(HoneypotMixin, forms.ModelForm):
    application_mode = forms.ChoiceField(
        choices=JobApplication.MODE_CHOICES, widget=forms.RadioSelect, initial="cv", label="How would you like to apply?",
    )
    cv = forms.FileField(required=False, label="CV or resume", help_text="PDF or DOCX, up to 5 MB.")
    consent = forms.BooleanField(
        required=True,
        label="I consent to Zencraft Solution storing my application and CV to assess me for this and similar roles. Unsuccessful applications are deleted after 6 months.",
    )

    class Meta:
        model = JobApplication
        fields = [
            "application_mode", "full_name", "email", "phone", "current_location", "years_experience",
            "notice_period", "expected_salary_npr", "source", "portfolio_url", "github_url", "linkedin_url",
            "cv", "headline", "professional_summary", "skills", "cover_letter", "consent",
        ]
        labels = {
            "years_experience": "Years of professional experience",
            "expected_salary_npr": "Expected monthly salary (NPR, optional)",
            "portfolio_url": "Portfolio or personal site",
            "github_url": "GitHub profile",
            "linkedin_url": "LinkedIn profile",
            "headline": "Professional headline",
            "professional_summary": "Short summary about you",
            "skills": "Key skills",
            "source": "Where did you hear about this role?",
            "cover_letter": "Cover letter (optional)",
        }
        help_texts = {
            "skills": "Separate with commas, for example: Python, Django, PostgreSQL, Docker",
            "headline": "For example: Junior Django developer with two internship projects",
        }
        widgets = {
            "years_experience": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "40"}),
            "professional_summary": forms.Textarea(attrs={"rows": 4}),
            "cover_letter": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, job=None, **kwargs):
        self.job = job
        super().__init__(*args, **kwargs)
        self.fields["expected_salary_npr"].widget.attrs.update({"min": "0", "step": "1000"})

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv:
            validate_document(cv)
        return cv

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("application_mode")
        if mode == "cv" and not cleaned.get("cv"):
            self.add_error("cv", "Please attach your CV, or switch to filling it in manually.")
        if mode == "manual":
            for name in ("headline", "professional_summary", "skills"):
                if not cleaned.get(name):
                    self.add_error(name, "This field is required when filling in your CV manually.")
        email = cleaned.get("email")
        if email and self.job:
            recent = JobApplication.objects.filter(
                job=self.job, email__iexact=email, created_at__gte=timezone.now() - timedelta(days=30)
            ).exists()
            if recent:
                self.add_error("email", "You have already applied for this role in the last 30 days. We will be in touch.")
        return cleaned


class EducationForm(forms.ModelForm):
    class Meta:
        model = EducationEntry
        fields = ["institution", "degree", "field_of_study", "start_year", "end_year", "grade"]
        widgets = {
            "start_year": forms.NumberInput(attrs={"min": "1970", "max": "2035"}),
            "end_year": forms.NumberInput(attrs={"min": "1970", "max": "2035"}),
        }
        labels = {"grade": "Grade or GPA", "end_year": "End year (or expected)"}


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = ExperienceEntry
        fields = ["company", "title", "start_date", "end_date", "is_current", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "month"}),
            "end_date": forms.DateInput(attrs={"type": "month"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"title": "Job title", "is_current": "I currently work here", "description": "What did you work on?"}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = ProjectEntry
        fields = ["name", "url", "tech_used", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}
        labels = {"name": "Project name", "url": "Link (optional)", "tech_used": "Technologies used"}


EducationFormSet = inlineformset_factory(JobApplication, EducationEntry, form=EducationForm, extra=1, max_num=6, can_delete=False)
ExperienceFormSet = inlineformset_factory(JobApplication, ExperienceEntry, form=ExperienceForm, extra=1, max_num=8, can_delete=False)
ProjectFormSet = inlineformset_factory(JobApplication, ProjectEntry, form=ProjectForm, extra=1, max_num=6, can_delete=False)
