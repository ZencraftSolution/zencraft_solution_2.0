from datetime import timedelta

from django import forms
from django.conf import settings
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.core.forms import HoneypotMixin
from apps.core.uploads import ScannerUnavailable, validate_document

from .models import EducationEntry, ExperienceEntry, JobApplication, ProjectEntry


def duplicate_message():
    days = settings.CAREERS_REAPPLY_DAYS
    return (
        f"We already have an application for this role from this email address within the last {days} days. "
        f"You can apply again after that, or write to us if you need to update the one we have."
    )


def recent_application(job, email):
    """The application that blocks a new one, if there is one.

    Deliberately a rolling window rather than a permanent block: with a permanent block anyone
    could type a real candidate's address into step 1 of a role and shut them out of it for good.
    """
    cleaned = (email or "").strip()
    if not cleaned:
        return None
    cutoff = timezone.now() - timedelta(days=settings.CAREERS_REAPPLY_DAYS)
    return JobApplication.objects.filter(job=job, email__iexact=cleaned, created_at__gte=cutoff).first()


class ApplyEmailForm(HoneypotMixin, forms.Form):
    """Step one: the address we reply to.

    It deliberately does NOT check whether that address has applied before. Doing so would turn
    an open form into an oracle for "has this person applied for this job?", which is exactly the
    sort of question an employer, a recruiter or a nosy colleague should not be able to ask.
    The duplicate rule is enforced at the end instead, after the form has been filled in.
    """

    email = forms.EmailField(
        label="Your email address",
        help_text="Your application reference and every update go to this address.",
    )

    def __init__(self, *args, job=None, **kwargs):
        self.job = job
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"autocomplete": "email", "autofocus": True, "placeholder": "you@example.com"})

    def clean_email(self):
        return self.cleaned_data["email"].strip()


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

    def __init__(self, *args, job=None, locked_email="", **kwargs):
        self.job = job
        self.locked_email = locked_email
        super().__init__(*args, **kwargs)
        self.fields["expected_salary_npr"].widget.attrs.update({"min": "0", "step": "1000"})
        if locked_email:
            # Confirmed in step one, so it is shown back but not editable here.
            self.fields["email"].initial = locked_email
            self.fields["email"].widget.attrs.update({"readonly": True, "tabindex": "-1"})
            self.fields["email"].help_text = "Confirmed in step 1. Go back to that step to use a different address."

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv:
            try:
                validate_document(cv)
            except ScannerUnavailable as exc:
                # Nothing the applicant did wrong, and nothing they can fix by retrying the same
                # file, so send them to the path that does not need a scanner at all.
                raise forms.ValidationError(
                    "We could not check your CV for viruses just now, so we have not accepted it. "
                    "Please try again in a few minutes, or choose \u201cFill in my CV manually\u201d above "
                    "and tell us about your experience here instead. We review both the same way."
                ) from exc
        return cv

    def clean_email(self):
        # The locked address wins, so editing the read-only field in the browser changes nothing.
        email = (self.locked_email or self.cleaned_data["email"]).strip()
        if recent_application(self.job, email):
            raise forms.ValidationError(duplicate_message())
        return email

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("application_mode")
        if mode == "cv" and not cleaned.get("cv"):
            self.add_error("cv", "Please attach your CV, or switch to filling it in manually.")
        if mode == "manual":
            for name in ("headline", "professional_summary", "skills"):
                if not cleaned.get(name):
                    self.add_error(name, "This field is required when filling in your CV manually.")
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
