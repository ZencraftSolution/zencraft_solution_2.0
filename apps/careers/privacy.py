"""Answering an applicant who asks "what do you hold on me?" or "please delete it".

Both are requests a person can make, and both have to be answerable without a developer and a
database shell. The export is everything stored about one application; the erase is the same
redaction the scheduled purge performs, run on demand.
"""

from django.utils import timezone


def export_application(application):
    """Everything held about one application, as plain data."""
    return {
        "exported_at": timezone.now().isoformat(),
        "reference": application.reference,
        "role": application.job.title,
        "applied_at": application.created_at.isoformat(),
        "status": application.get_status_display(),
        "about_you": {
            "full_name": application.full_name,
            "email": application.email,
            "phone": application.phone,
            "current_location": application.current_location,
            "years_experience": str(application.years_experience),
            "notice_period": application.get_notice_period_display(),
            "expected_salary_npr": str(application.expected_salary_npr) if application.expected_salary_npr else None,
            "heard_about_us_via": application.get_source_display(),
        },
        "links": {
            "portfolio": application.portfolio_url,
            "github": application.github_url,
            "linkedin": application.linkedin_url,
        },
        "application": {
            "how_you_applied": application.get_application_mode_display(),
            "cv_filename": application.cv_original_name,
            "headline": application.headline,
            "professional_summary": application.professional_summary,
            "skills": application.skill_list,
            "cover_letter": application.cover_letter,
        },
        "education": [
            {
                "institution": e.institution, "degree": e.degree, "field_of_study": e.field_of_study,
                "start_year": e.start_year, "end_year": e.end_year, "grade": e.grade,
            }
            for e in application.education.all()
        ],
        "experience": [
            {
                "company": x.company, "title": x.title, "start_date": str(x.start_date),
                "end_date": str(x.end_date) if x.end_date else None, "is_current": x.is_current,
                "description": x.description,
            }
            for x in application.experience.all()
        ],
        "projects": [
            {"name": p.name, "url": p.url, "tech_used": p.tech_used, "description": p.description}
            for p in application.projects.all()
        ],
        "consent": {
            "given": application.consent,
            "given_at": application.consent_at.isoformat() if application.consent_at else None,
        },
        # Internal hiring notes are our own assessment, not the applicant's data, and are not included.
        "notes_held": application.notes.count(),
        "erased_at": application.purged_at.isoformat() if application.purged_at else None,
    }


def erase_application(application):
    """Removes the personal data but keeps the row, so hiring statistics stay honest.

    The same redaction purge_applications performs on a schedule. The reference, the role, the
    dates and the outcome remain; everything that identifies a person does not.
    """
    if application.cv:
        application.cv.delete(save=False)
    application.education.all().delete()
    application.experience.all().delete()
    application.projects.all().delete()
    application.notes.all().delete()
    application.full_name = "Erased at the applicant's request"
    application.email = f"erased-{application.pk}@invalid.local"
    application.phone = ""
    application.current_location = ""
    application.cover_letter = application.headline = application.professional_summary = application.skills = ""
    application.portfolio_url = application.github_url = application.linkedin_url = ""
    application.cv_original_name = ""
    application.purged_at = timezone.now()
    application.save()
    return application
