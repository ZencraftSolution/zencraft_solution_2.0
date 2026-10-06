"""schema.org structured data, built in Python rather than hand-written into templates.

Hand-written JSON inside a template is how the job pages ended up with a different @context from
every other page: nothing checks a string. Building it here means each block has one shape, the
tests can parse it, and a field that moves on a model breaks the build rather than the rich result.
"""

from django.urls import reverse

from .seo import absolute, site_url, truncate_description

CONTEXT = "https://schema.org"

# schema.org's vocabulary for the employment types this site offers.
EMPLOYMENT_TYPES = {
    "full-time": "FULL_TIME",
    "part-time": "PART_TIME",
    "contract": "CONTRACTOR",
    "internship": "INTERN",
    "temporary": "TEMPORARY",
}


def _clean(data):
    """Drops empty values, so a missing optional field is absent rather than null."""
    if isinstance(data, dict):
        return {key: _clean(value) for key, value in data.items() if value not in (None, "", [], {})}
    if isinstance(data, list):
        return [_clean(item) for item in data if item not in (None, "", [], {})]
    return data


def organization(site):
    """The company itself. sameAs is what ties the site to its social profiles for Google."""
    profiles = [site.linkedin_url, site.facebook_url, site.instagram_url, site.tiktok_url, site.github_url, site.x_url]
    return _clean({
        "@context": CONTEXT,
        "@type": "Organization",
        "@id": f"{site_url()}/#organization",
        "name": site.company_name,
        "url": site_url(),
        "logo": absolute("/static/img/logo.png"),
        "image": absolute(site.share_image_src),
        "description": site.tagline,
        "email": site.email,
        "telephone": site.phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": site.address,
            "addressCountry": "NP",
        },
        "sameAs": [url for url in profiles if url],
    })


def website(site):
    """The site, and how a search engine can offer a search box straight into it."""
    return {
        "@context": CONTEXT,
        "@type": "WebSite",
        "@id": f"{site_url()}/#website",
        "name": site.company_name,
        "url": site_url(),
        "publisher": {"@id": f"{site_url()}/#organization"},
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{site_url()}{reverse('core:search')}?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumbs(items):
    """items: [(label, url_or_empty), ...] in order, the last being the current page."""
    return {
        "@context": CONTEXT,
        "@type": "BreadcrumbList",
        "itemListElement": [
            _clean({
                "@type": "ListItem",
                "position": position,
                "name": label,
                "item": absolute(url) if url else None,
            })
            for position, (label, url) in enumerate(items, start=1)
        ],
    }


def service(obj, site):
    return _clean({
        "@context": CONTEXT,
        "@type": "Service",
        "name": obj.name,
        "serviceType": obj.name,
        "description": truncate_description(obj.summary),
        "url": absolute(obj.get_absolute_url()),
        "image": absolute(obj.hero_image_url),
        "provider": {"@id": f"{site_url()}/#organization"},
        "areaServed": [{"@type": "Country", "name": "Nepal"}, {"@type": "Place", "name": "Worldwide"}],
        "brand": {"@type": "Brand", "name": site.company_name},
    })


def article(post, site):
    return _clean({
        "@context": CONTEXT,
        "@type": "BlogPosting",
        "headline": post.title[:110],
        "description": truncate_description(post.seo_description or post.excerpt),
        "image": absolute(post.hero_image_url),
        "datePublished": post.published_at.isoformat(),
        "dateModified": post.published_at.isoformat(),
        "url": absolute(post.get_absolute_url()),
        "mainEntityOfPage": {"@type": "WebPage", "@id": absolute(post.get_absolute_url())},
        "author": {"@type": "Person", "name": post.author.name} if post.author else {"@id": f"{site_url()}/#organization"},
        "publisher": {"@id": f"{site_url()}/#organization"},
        "keywords": ", ".join(post.tag_list) if post.tag_list else None,
        "wordCount": None,
    })


def job_posting(job, site):
    """A JobPosting Google will accept, including the remote-work shape it expects."""
    data = {
        "@context": CONTEXT,
        "@type": "JobPosting",
        "title": job.title,
        "description": truncate_description(job.description, 5000) or job.summary,
        "datePosted": job.posted_at.isoformat(),
        "validThrough": job.closing_date.isoformat() if job.closing_date else None,
        "employmentType": EMPLOYMENT_TYPES.get(job.employment_type, "OTHER"),
        "url": absolute(job.get_absolute_url()),
        "directApply": True,
        "hiringOrganization": {
            "@type": "Organization",
            "name": site.company_name,
            "sameAs": site_url(),
            "logo": absolute("/static/img/logo.png"),
        },
        "industry": "Software development",
    }
    if job.work_mode == "remote":
        # Google requires this shape for a role with no office to go to.
        data["jobLocationType"] = "TELECOMMUTE"
        data["applicantLocationRequirements"] = {"@type": "Country", "name": "Nepal"}
    else:
        data["jobLocation"] = {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": site.address,
                "addressLocality": "Rupandehi",
                "addressCountry": "NP",
            },
        }
    if job.show_salary and job.salary_min_npr and job.salary_max_npr:
        data["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": "NPR",
            "value": {
                "@type": "QuantitativeValue",
                "minValue": float(job.salary_min_npr),
                "maxValue": float(job.salary_max_npr),
                "unitText": "MONTH",
            },
        }
    return _clean(data)


def product(obj, site, price_npr=None):
    return _clean({
        "@context": CONTEXT,
        "@type": "Product",
        "name": obj.name,
        "description": truncate_description(obj.summary),
        "url": absolute(obj.get_absolute_url()),
        "brand": {"@type": "Brand", "name": site.company_name},
        "offers": {
            "@type": "Offer",
            "priceCurrency": "NPR",
            "price": f"{price_npr if price_npr is not None else obj.price_npr:.0f}",
            "availability": "https://schema.org/InStock",
            "url": absolute(obj.get_absolute_url()),
            "seller": {"@id": f"{site_url()}/#organization"},
        },
    })


def faq_page(faqs):
    """Only emitted when there are real questions on the page; an empty FAQPage is a penalty."""
    questions = [
        {
            "@type": "Question",
            "name": faq.question,
            "acceptedAnswer": {"@type": "Answer", "text": truncate_description(faq.answer, 1200)},
        }
        for faq in faqs
    ]
    if not questions:
        return None
    return {"@context": CONTEXT, "@type": "FAQPage", "mainEntity": questions}


def case_study(case, site):
    return _clean({
        "@context": CONTEXT,
        "@type": "Article",
        "headline": case.title[:110],
        "description": truncate_description(case.seo_description or case.summary),
        "image": absolute(case.cover_image_url),
        "url": absolute(case.get_absolute_url()),
        "mainEntityOfPage": {"@type": "WebPage", "@id": absolute(case.get_absolute_url())},
        "author": {"@id": f"{site_url()}/#organization"},
        "publisher": {"@id": f"{site_url()}/#organization"},
        "datePublished": f"{case.year}-01-01" if getattr(case, "year", None) else None,
        "about": case.industry.name if case.industry_id else None,
    })
