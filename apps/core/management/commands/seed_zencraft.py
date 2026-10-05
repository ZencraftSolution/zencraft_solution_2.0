from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.blog.models import BlogCategory, BlogPost
from apps.careers.models import Department, JobOpening
from apps.commerce.models import EngagementModel, FixedPriceRange, ProductizedService, RoleRate
from apps.core import seed_content as C
from apps.core import seed_services as S
from apps.core.models import SiteSettings
from apps.estimator.models import EstimatorConfig, FeatureOption, ProjectType
from apps.portfolio.models import CaseStudy, GalleryImage, TeamMember, Testimonial
from apps.services.models import FAQ, Industry, ProcessStep, Service, ServiceCategory, Technology
from config.settings import env


class Command(BaseCommand):
    help = "Loads Zencraft Solution seed content. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        SiteSettings.objects.get_or_create(pk=1)
        self.seed_technologies()
        self.seed_industries()
        self.seed_commercial()
        self.seed_services()
        self.seed_estimator()
        self.seed_portfolio()
        self.seed_careers()
        self.seed_blog()
        self.seed_admin()
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Zencraft seed data loaded."))

    def seed_technologies(self):
        for order, (name, slug, category, logo, prof, years) in enumerate(S.TECHNOLOGIES):
            Technology.objects.update_or_create(slug=slug, defaults=dict(name=name, category=category, logo_url=logo, proficiency=prof, years_used=years, order=order))
        self.stdout.write(f"  technologies: {len(S.TECHNOLOGIES)}")

    def seed_industries(self):
        ct = ContentType.objects.get_for_model(Industry)
        for order, data in enumerate(S.INDUSTRIES):
            industry, _ = Industry.objects.update_or_create(slug=data["slug"], defaults=dict(
                name=data["name"], icon=data["icon"], tagline=data["tagline"], description=data["description"],
                challenges=data["challenges"], solutions=data["solutions"], image_url=data["image"], order=order,
            ))
            FAQ.objects.filter(content_type=ct, object_id=industry.pk).delete()
            for i, (q, a) in enumerate(data.get("faqs", [])):
                FAQ.objects.create(content_type=ct, object_id=industry.pk, question=q, answer=a, order=i)
        self.stdout.write(f"  industries: {len(S.INDUSTRIES)}")

    def seed_commercial(self):
        for order, m in enumerate(C.ENGAGEMENT_MODELS):
            EngagementModel.objects.update_or_create(slug=m["slug"], defaults=dict(
                name=m["name"], kind=m["kind"], icon=m["icon"], summary=m["summary"], best_for=m["best_for"],
                how_it_works=m["how_it_works"], advantages=m["advantages"], billing_note=m["billing_note"], order=order,
            ))
        RoleRate.objects.all().delete()
        for order, (role, band, hourly, monthly) in enumerate(C.ROLE_RATES):
            RoleRate.objects.create(role=role, experience_band=band, hourly_rate_npr=Decimal(hourly), monthly_rate_npr=Decimal(monthly), order=order)
        FixedPriceRange.objects.all().delete()
        for order, (ptype, desc, low, high, timeline) in enumerate(C.FIXED_RANGES):
            FixedPriceRange.objects.create(project_type=ptype, description=desc, min_npr=Decimal(low), max_npr=Decimal(high), typical_timeline=timeline, order=order)
        for order, p in enumerate(C.PRODUCTS):
            ProductizedService.objects.update_or_create(slug=p["slug"], defaults=dict(
                name=p["name"], tier_label=p["tier_label"], category=p["category"], icon=p["icon"], summary=p["summary"],
                description=p["description"], price_npr=Decimal(p["price"]), billing=p["billing"], deliverables=p["deliverables"],
                duration=p["duration"], sla=p["sla"], featured=p["featured"], is_active=True, order=order,
            ))
        self.stdout.write("  engagement models, rates and store products")

    def seed_services(self):
        category, _ = ServiceCategory.objects.get_or_create(slug="services", defaults={"name": "Services"})
        ct = ContentType.objects.get_for_model(Service)
        created = {}
        for order, data in enumerate(S.SERVICES):
            service, _ = Service.objects.update_or_create(slug=data["slug"], defaults=dict(
                category=category, name=data["name"], icon=data["icon"], nav_blurb=data["nav_blurb"],
                outcome_headline=data["headline"], summary=data["summary"], intro=data["intro"], hero_image_url=data["image"],
                deliverables=[{"title": t, "text": x} for t, x in data["deliverables"]],
                seo_title=f"{data['name']} company in Nepal | Zencraft Solution"[:70],
                seo_description=data["summary"][:160], order=order, featured=order < 3, is_published=True,
            ))
            service.technologies.set(Technology.objects.filter(slug__in=data["techs"]))
            service.industries.set(Industry.objects.filter(slug__in=data["industries"]))
            service.engagement_models.set(EngagementModel.objects.filter(kind__in=data["models"]))
            service.steps.all().delete()
            for i, (title, desc, hint) in enumerate(data["steps"]):
                ProcessStep.objects.create(service=service, order=i, title=title, description=desc, duration_hint=hint)
            FAQ.objects.filter(content_type=ct, object_id=service.pk).delete()
            for i, (q, a) in enumerate(data["faqs"]):
                FAQ.objects.create(content_type=ct, object_id=service.pk, question=q, answer=a, order=i)
            created[data["slug"]] = service
        for data in S.SERVICES:
            created[data["slug"]].related.set([created[s] for s in data["related"] if s in created])
        self.stdout.write(f"  services: {len(S.SERVICES)}")

    def seed_estimator(self):
        EstimatorConfig.load()
        types = {}
        for order, (key, label, desc, icon, hours) in enumerate(C.PROJECT_TYPES):
            types[key], _ = ProjectType.objects.update_or_create(key=key, defaults=dict(label=label, description=desc, icon=icon, base_hours=hours, order=order, is_active=True))
        for order, (key, label, help_text, hours, applies) in enumerate(C.FEATURES):
            feature, _ = FeatureOption.objects.update_or_create(key=key, defaults=dict(label=label, help_text=help_text, hours=hours, order=order, is_active=True))
            feature.project_types.set([types[k] for k in applies])
        self.stdout.write("  estimator configuration")

    def seed_portfolio(self):
        for order, data in enumerate(C.CASE_STUDIES):
            case, _ = CaseStudy.objects.update_or_create(slug=data["slug"], defaults=dict(
                title=data["title"], client_name=data["client"], is_anonymized=data["anonymized"],
                industry=Industry.objects.filter(slug=data["industry"]).first(), summary=data["summary"], challenge=data["challenge"],
                solution=data["solution"], results=data["results"], architecture_note=data["architecture"],
                code_language=data["code_language"], code_snippet=data["code"], cover_image_url=data["cover"],
                duration=data["duration"], team_size=data["team"], year=data["year"], featured=data["featured"], is_published=True, order=order,
            ))
            case.services.set(Service.objects.filter(slug__in=data["services"]))
            case.technologies.set(Technology.objects.filter(slug__in=data["techs"]))
            case.images.all().delete()
            case.images.create(image_url=data["cover"].replace("h=1000", "h=900"), caption="Production release", order=0)

        Testimonial.objects.all().delete()
        for order, (name, role, company, photo, rating, content, case_slug) in enumerate(C.TESTIMONIALS):
            Testimonial.objects.create(client_name=name, role=role, company=company, photo_url=photo, rating=rating, content=content,
                                       case_study=CaseStudy.objects.filter(slug=case_slug).first(), verification="verified", featured=True, order=order)
        TeamMember.objects.all().delete()
        for order, (name, role, lead, photo, bio) in enumerate(C.TEAM):
            TeamMember.objects.create(name=name, role=role, is_leadership=lead, photo_url=photo, bio=bio, order=order, linkedin_url="https://www.linkedin.com")
        GalleryImage.objects.all().delete()
        for order, (url, caption, cat) in enumerate(C.GALLERY):
            GalleryImage.objects.create(image_url=url, caption=caption, category=cat, order=order)
        self.stdout.write(f"  case studies: {len(C.CASE_STUDIES)}, testimonials, team, gallery")

    def seed_careers(self):
        depts = {}
        for order, (name, slug) in enumerate(C.DEPARTMENTS):
            depts[slug], _ = Department.objects.update_or_create(slug=slug, defaults={"name": name, "order": order})
        today = timezone.localdate()
        for i, j in enumerate(C.JOBS):
            job, _ = JobOpening.objects.update_or_create(slug=j["slug"], defaults=dict(
                title=j["title"], department=depts[j["dept"]], work_mode=j["mode"], employment_type=j["type"],
                experience_level=j["level"], experience_years=j["years"], summary=j["summary"], description=j["description"],
                responsibilities=j["responsibilities"], requirements=j["requirements"], nice_to_haves=j["nice"],
                growth_path=j["growth"], salary_min_npr=Decimal(j["salary"][0]), salary_max_npr=Decimal(j["salary"][1]),
                show_salary=True, is_active=True, posted_at=today - timedelta(days=3 + i * 4), closing_date=today + timedelta(days=30 + i * 5),
            ))
            job.tech_stack.set(Technology.objects.filter(slug__in=j["techs"]))
        self.stdout.write(f"  jobs: {len(C.JOBS)}")

    def seed_blog(self):
        cats = {}
        for order, (name, slug) in enumerate(C.BLOG_CATEGORIES):
            cats[slug], _ = BlogCategory.objects.update_or_create(slug=slug, defaults={"name": name, "order": order})
        now = timezone.now()
        for i, p in enumerate(C.BLOG_POSTS):
            BlogPost.objects.update_or_create(slug=p["slug"], defaults=dict(
                title=p["title"], category=cats[p["category"]], author=TeamMember.objects.filter(name=p["author"]).first(),
                tags=p["tags"], excerpt=p["excerpt"], body=p["body"], hero_image_url=p["image"], is_published=True,
                published_at=now - timedelta(days=4 + i * 9), seo_description=p["excerpt"][:160],
            ))
        self.stdout.write(f"  blog posts: {len(C.BLOG_POSTS)}")

    def seed_admin(self):
        User = get_user_model()
        password = env.str("ADMIN_SEED_PASSWORD", default="")
        if not password:
            self.stdout.write("  skipped admin user (ADMIN_SEED_PASSWORD not set)")
            return
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@zencraftsolution.com", password, first_name="Site", last_name="Admin", job_title="Administrator")
            self.stdout.write("  created superuser: admin")
