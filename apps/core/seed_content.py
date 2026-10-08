"""Seed content: commercial models, estimator engine, portfolio, people, careers and insights."""
from .seed_services import U

ENGAGEMENT_MODELS = [
    {
        "slug": "dedicated-team", "name": "Dedicated team", "kind": "dedicated", "icon": "users-three",
        "summary": "A long-term team of engineers, QA and a project manager who work only on your product.",
        "best_for": "Product companies and enterprises with an ongoing roadmap and changing priorities.",
        "how_it_works": "You choose the roles and seniority. We recruit or assign, onboard them to your tools and rituals, and handle payroll, equipment and retention. You direct the work day to day. Scale up or down with 30 days notice.",
        "advantages": ["Monthly rate per role, published below", "Your processes, your backlog, your tools", "Replacement within 3 weeks if someone leaves", "Minimum commitment of 3 months"],
        "billing_note": "Billed monthly per team member",
    },
    {
        "slug": "time-and-materials", "name": "Time and materials", "kind": "tm", "icon": "clock-countdown",
        "summary": "Pay for the hours actually worked, with full visibility into timesheets and progress.",
        "best_for": "Projects where scope will evolve, early-stage products and ongoing improvements.",
        "how_it_works": "We agree a monthly budget cap and a prioritised backlog. The team logs time against tasks you can see in real time. You can reprioritise every sprint without renegotiating a contract.",
        "advantages": ["Hourly rates by role, published below", "Weekly timesheets and burn-down reports", "Budget cap you control", "No change-request paperwork"],
        "billing_note": "Billed monthly on logged hours",
    },
    {
        "slug": "fixed-price", "name": "Fixed price", "kind": "fixed", "icon": "clipboard-text",
        "summary": "An agreed scope, timeline and price, with milestone payments tied to working deliverables.",
        "best_for": "Well-defined projects, MVPs with a clear scope and organisations that need budget certainty.",
        "how_it_works": "Every fixed-price project starts with a paid discovery workshop that produces a detailed specification. We then quote a fixed price with milestone payments, typically 30 percent at start and the rest across delivery milestones.",
        "advantages": ["Budget certainty for the agreed scope", "Milestone payments on accepted deliverables", "Warranty period of 60 days after launch", "Change requests quoted before work starts"],
        "billing_note": "Indicative ranges below, final quote after discovery",
    },
    {
        "slug": "retainer-support", "name": "Retainer and support", "kind": "retainer", "icon": "lifebuoy",
        "summary": "A fixed monthly plan for maintenance, support and small improvements with guaranteed response times.",
        "best_for": "Live systems that need monitoring, security updates and a team on call.",
        "how_it_works": "Choose a plan by hours and response time. We monitor your systems, apply updates, fix issues and use remaining hours for improvements you prioritise. Plans are month to month after the first quarter.",
        "advantages": ["Fixed monthly fee", "SLA-backed response times", "Monthly service report", "Buy directly from our store"],
        "billing_note": "Fixed monthly plans, purchasable online",
    },
]

ROLE_RATES = [
    ("Junior developer", "0 to 2 years", 1100, 165000),
    ("Mid-level developer", "2 to 5 years", 1650, 250000),
    ("Senior developer", "5+ years", 2400, 360000),
    ("QA engineer", "2 to 5 years", 1250, 190000),
    ("DevOps engineer", "3+ years", 2300, 345000),
    ("UI/UX designer", "3+ years", 1700, 255000),
    ("Project manager", "5+ years", 2200, 330000),
]

FIXED_RANGES = [
    ("Company website", "Content-managed marketing site with up to 15 pages, blog and contact forms.", 60000, 250000, "3 to 6 weeks"),
    ("E-commerce store", "Custom storefront with catalogue, local payments, delivery and admin dashboard.", 350000, 1200000, "8 to 14 weeks"),
    ("Mobile app MVP", "Cross-platform iOS and Android app with backend, admin panel and store release.", 600000, 1800000, "10 to 16 weeks"),
    ("Web application or portal", "Customer or partner portal with accounts, roles, workflows and reporting.", 800000, 2500000, "12 to 20 weeks"),
    ("ERP or internal system module", "Inventory, HR, procurement or production module integrated with accounting.", 900000, 3500000, "12 to 24 weeks"),
    ("Data warehouse and dashboards", "Pipelines from 3 to 6 sources, modelled warehouse and management dashboards.", 700000, 2200000, "8 to 16 weeks"),
]

PRODUCTS = [
    # helpdesk
    dict(slug="help-desk-bronze", name="Help Desk", tier_label="Bronze", category="helpdesk", icon="headset", price=45000, billing="monthly",
         summary="Business-hours support for teams of up to 25 people.",
         description="Email and phone support during office hours for your employees, covering access, devices, email and common business software. Includes a shared knowledge base and a monthly service report.",
         deliverables=["Up to 100 tickets per month", "Sun to Fri, 9:30 to 18:00 NPT", "4-hour first response", "Monthly service report"], duration="Month to month", sla="8x5, 4h response", featured=False),
    dict(slug="help-desk-silver", name="Help Desk", tier_label="Silver", category="helpdesk", icon="headset", price=95000, billing="monthly",
         summary="Extended hours and application support for growing companies.",
         description="Multichannel support including chat and WhatsApp, with L2 application support for up to two business applications and remote device management.",
         deliverables=["Up to 300 tickets per month", "7:00 to 22:00 NPT, 6 days", "1-hour first response", "L2 support for 2 applications", "Remote device management"], duration="Month to month", sla="15x6, 1h response", featured=True),
    dict(slug="help-desk-gold", name="Help Desk", tier_label="Gold", category="helpdesk", icon="headset", price=185000, billing="monthly",
         summary="Round-the-clock support with engineers on call for critical systems.",
         description="24/7 coverage for employees or customers with L3 engineering escalation, a named service manager and quarterly improvement workshops.",
         deliverables=["Up to 800 tickets per month", "24/7/365 coverage", "15-minute response for critical issues", "L3 engineering escalation", "Named service manager"], duration="Quarterly minimum", sla="24x7, 15m critical", featured=False),
    # maintenance
    dict(slug="website-care-essential", name="Website Care", tier_label="Essential", category="maintenance", icon="wrench", price=18000, billing="monthly",
         summary="Updates, backups and monitoring for business websites.",
         description="We keep your website secure and online with core and plugin updates, daily off-site backups, uptime monitoring and up to three hours of small content changes each month.",
         deliverables=["Security and plugin updates", "Daily off-site backups", "Uptime monitoring", "3 hours of changes per month"], duration="Month to month", sla="Next business day", featured=False),
    dict(slug="website-care-growth", name="Website Care", tier_label="Growth", category="maintenance", icon="wrench", price=38000, billing="monthly",
         summary="Maintenance plus performance, SEO health and monthly improvements.",
         description="Everything in Essential, plus performance tuning, monthly technical SEO checks, conversion tracking and ten hours of development for improvements you choose.",
         deliverables=["Everything in Essential", "Monthly performance and SEO report", "10 hours of development", "4-hour response on outages"], duration="Month to month", sla="4h outage response", featured=True),
    # audits
    dict(slug="security-audit", name="Application Security Audit", tier_label="", category="audit", icon="shield-check", price=150000, billing="one_time",
         summary="Find exploitable weaknesses before attackers do.",
         description="A two-week security assessment of one web or mobile application covering the OWASP Top 10, authentication, authorisation, data exposure and infrastructure configuration, with a retest after fixes.",
         deliverables=["OWASP Top 10 and API testing", "Authentication and session review", "Severity-rated findings report", "Developer walkthrough call", "Free retest within 60 days"], duration="10 working days", sla="", featured=True),
    dict(slug="code-quality-audit", name="Code Quality Audit", tier_label="", category="audit", icon="code", price=90000, billing="one_time",
         summary="An independent view of maintainability, test coverage and technical debt.",
         description="Senior engineers review your repository, architecture and delivery pipeline, then deliver a prioritised report on risks, quick wins and a remediation roadmap.",
         deliverables=["Architecture and code review", "Dependency and licence scan", "Test coverage analysis", "Prioritised remediation roadmap"], duration="7 working days", sla="", featured=False),
    # assessments
    dict(slug="performance-audit", name="Performance Optimization Audit", tier_label="", category="assessment", icon="gauge", price=75000, billing="one_time",
         summary="Find out why your site or API is slow and exactly what to fix.",
         description="Front-end Core Web Vitals analysis, back-end profiling, database query review and a load test that shows where your system breaks, with a prioritised fix list.",
         deliverables=["Core Web Vitals analysis", "API and database profiling", "Load test up to 2,000 virtual users", "Prioritised fix list with effort estimates"], duration="5 working days", sla="", featured=False),
    dict(slug="cloud-migration-assessment", name="Cloud Migration Assessment", tier_label="", category="assessment", icon="cloud-arrow-up", price=120000, billing="one_time",
         summary="A costed, risk-rated plan for moving to the cloud.",
         description="We inventory your workloads, model costs on AWS, Azure and Google Cloud, identify dependencies and risks, and deliver a phased migration plan you can execute with us or anyone else.",
         deliverables=["Workload and dependency inventory", "Three-provider cost comparison", "Security and compliance review", "Phased migration plan"], duration="10 working days", sla="", featured=False),
    # consultation
    dict(slug="discovery-workshop", name="Discovery Workshop", tier_label="2 days", category="consultation", icon="presentation-chart", price=60000, billing="one_time",
         summary="Turn an idea into a scoped plan, estimate and prototype.",
         description="Two facilitated days with our product lead, architect and designer. You leave with prioritised requirements, a clickable prototype of key screens, an architecture outline and a fixed-price quote. The workshop fee is credited against the project if you proceed within 60 days.",
         deliverables=["Stakeholder and user workshop", "Prioritised feature backlog", "Clickable prototype of key screens", "Architecture outline", "Fixed quote, fee credited if you proceed"], duration="2 days plus 3 days reporting", sla="", featured=True),
    dict(slug="technical-consultation", name="Technical Consultation", tier_label="90 minutes", category="consultation", icon="chats-circle", price=8500, billing="one_time",
         summary="Ninety minutes with a senior architect on the question keeping you up at night.",
         description="A focused video call on architecture, technology choice, scaling, security or vendor proposals, followed by a written summary of recommendations.",
         deliverables=["90-minute video session", "Senior architect or tech lead", "Written summary within 2 days"], duration="90 minutes", sla="", featured=False),
]

PROJECT_TYPES = [
    ("web-app", "Web application", "Portals, SaaS products and internal tools used in a browser", "browsers", 320),
    ("mobile-app", "Mobile app", "iOS and Android apps with a backend", "device-mobile", 380),
    ("desktop-software", "Desktop software", "Windows, macOS or Linux applications", "desktop-tower", 360),
    ("data-platform", "Data platform", "Pipelines, warehouse, dashboards and models", "chart-line-up", 420),
    ("ecommerce", "E-commerce", "Online store with payments and fulfilment", "storefront", 300),
    ("integration", "System integration", "Connecting ERPs, payment providers and third-party APIs", "plugs-connected", 160),
    ("modernization", "Modernization", "Upgrading or migrating an existing system", "arrows-clockwise", 280),
]

ALL = [t[0] for t in PROJECT_TYPES]
FEATURES = [
    ("auth", "User accounts and login", "Sign-up, login, password reset, social login", 40, ALL),
    ("roles", "Roles and permissions", "Different access levels for staff and customers", 60, ["web-app", "mobile-app", "desktop-software", "data-platform", "ecommerce", "modernization"]),
    ("sso", "Single sign-on", "Microsoft, Google Workspace or LDAP login", 60, ["web-app", "desktop-software", "integration", "modernization"]),
    ("payments", "Online payments", "eSewa, Khalti, Fonepay, cards or Stripe", 70, ["web-app", "mobile-app", "ecommerce"]),
    ("admin", "Admin panel", "Back-office dashboard to manage content and users", 90, ["web-app", "mobile-app", "desktop-software", "ecommerce", "data-platform"]),
    ("api", "Public or partner API", "Documented API for other systems or apps", 80, ["web-app", "mobile-app", "desktop-software", "integration", "modernization"]),
    ("realtime", "Real-time features", "Live chat, live tracking, collaborative editing", 110, ["web-app", "mobile-app", "desktop-software"]),
    ("notifications", "Notifications", "Email, SMS and push notifications", 45, ["web-app", "mobile-app", "ecommerce"]),
    ("reporting", "Reports and exports", "Scheduled reports, PDF and Excel exports", 100, ["web-app", "desktop-software", "data-platform", "ecommerce", "modernization"]),
    ("dashboards", "Analytics dashboards", "Charts and KPIs for management", 90, ["web-app", "data-platform"]),
    ("third-party", "Third-party integrations", "CRM, ERP, accounting or logistics APIs", 60, ALL),
    ("search", "Advanced search and filters", "Full-text search, facets and sorting", 55, ["web-app", "ecommerce", "data-platform"]),
    ("files", "File uploads and documents", "Upload, preview and manage documents", 35, ["web-app", "mobile-app", "desktop-software"]),
    ("maps", "Maps and location", "Geolocation, routes and map views", 65, ["web-app", "mobile-app"]),
    ("offline", "Offline mode", "Keep working without an internet connection", 120, ["mobile-app", "desktop-software"]),
    ("i18n", "Multiple languages", "Nepali, English and more", 50, ["web-app", "mobile-app", "desktop-software", "ecommerce"]),
    ("inventory", "Inventory and stock", "Stock levels across branches and warehouses", 120, ["ecommerce", "desktop-software"]),
    ("hardware", "Hardware integration", "Printers, scanners, scales, biometric devices", 130, ["desktop-software"]),
    ("etl", "Data pipelines", "Automated ingestion from several sources", 140, ["data-platform", "integration", "modernization"]),
    ("ml", "Machine learning models", "Forecasting, scoring or recommendations", 180, ["data-platform"]),
    ("migration", "Data migration", "Move data from an existing system", 110, ["modernization", "integration", "ecommerce", "data-platform"]),
    ("audit-trail", "Audit trail", "Record who changed what and when", 45, ["web-app", "desktop-software", "data-platform", "modernization"]),
]

CASE_STUDIES = [
    dict(
        slug="mobile-banking-development-bank", title="Mobile banking that moved 38% of branch visits online",
        client="A class B development bank", anonymized=True, industry="", services=["mobile-application-development", "web-development", "testing-qa"],
        techs=["flutter", "django", "postgresql", "redis", "kubernetes", "playwright"], year=2026, duration="5 months", team=6, featured=True,
        cover=U("photo-1563986768609-322da13575f3", 1600, 1000),
        summary="A Flutter banking app and API layer on top of a legacy core banking system, serving over 400,000 customers.",
        challenge="The bank's existing app was a thin wrapper around its internet banking site. It crashed on low-end Android phones, timed out during salary days and could not add features because every change required the core banking vendor.\n\nBranches were crowded with customers doing simple tasks like statement requests and fund transfers, and the bank was losing younger customers to wallets.",
        solution="We built an integration layer in Django that exposes safe, idempotent APIs over the core banking middleware, with Redis caching for balances and a queue for transfers so the app never waits on the core system.\n\nThe new Flutter app supports fund transfers, QR payments through Fonepay, bill payments, fixed deposit requests and card controls. Biometric login and device binding protect accounts, and a staged rollout moved customers over in four weeks.",
        architecture="Flutter client, Django API gateway on Kubernetes, Redis for caching and idempotency keys, Celery workers talking to core banking middleware, PostgreSQL for app data and a full audit trail.",
        results=[{"value": "412k", "label": "Active app users"}, {"value": "38%", "label": "Fewer routine branch visits"}, {"value": "99.9%", "label": "API uptime since launch"}, {"value": "4.6", "label": "Play Store rating, up from 2.1"}],
        code_language="python",
        code="""@transaction.atomic
def create_transfer(user, payload, idempotency_key):
    # Replaying the same key returns the original result instead of moving money twice
    existing = Transfer.objects.filter(idempotency_key=idempotency_key, user=user).first()
    if existing:
        return existing

    account = Account.objects.select_for_update().get(pk=payload.source_id, owner=user)
    if account.available_balance < payload.amount:
        raise InsufficientFunds()

    transfer = Transfer.objects.create(
        user=user, source=account, amount=payload.amount,
        destination=payload.destination, idempotency_key=idempotency_key,
        status=Transfer.Status.QUEUED,
    )
    post_to_core_banking.delay(transfer.pk)  # core system is slow, never block the app on it
    return transfer""",
    ),
]

TESTIMONIALS = [
    ("Sushma Karki", "Chief Digital Officer", "A class B development bank", U("photo-1573496359142-b8d87734a5a2", 200, 200), 5,
     "Zencraft understood our core banking limits better than the vendor did. The app launched on schedule and our branches are finally quieter.", "mobile-banking-development-bank"),
    ("Dr. Anil Shrestha", "Medical Director", "Teaching hospital, Kathmandu", U("photo-1612349317150-e413f6a5b16d", 200, 200), 5,
     "Doctors see full patient history in seconds now. The team sat with our counter staff for weeks, and it shows in how the system works.", "hospital-information-system"),
    ("Pratik Maharjan", "Head of E-commerce", "Kathmandu Kapda House", U("photo-1507003211169-0a1dd7228f2d", 200, 200), 5,
     "Our Dashain sale used to break the website. This year we did three times the orders and nobody on the team lost sleep.", "omnichannel-fashion-retail"),
    ("Nirajan Thapa", "Operations Director", "Trishuli Cargo Services", U("photo-1500648767791-00dcc994a43e", 200, 200), 5,
     "Dispatch used to be forty phone calls before breakfast. Now we see every truck on one screen and customers stopped calling to ask where their goods are.", "fleet-tracking-logistics"),
    ("Aarati Gurung", "General Manager", "Annapurna Heritage Hotels", U("photo-1544005313-94ddf0286df2", 200, 200), 5,
     "Their night shift answers faster than our old vendor did in the daytime. Moving to the cloud also cut our costs noticeably.", "hotel-group-cloud-support"),
    ("Rebecca Lindqvist", "Regional Operations Lead", "International development NGO", U("photo-1580489944761-15a19d654956", 200, 200), 4,
     "Monthly donor reporting went from a week of spreadsheet work to an afternoon. The numbers finally match across every report.", "ngo-program-analytics"),
]

# Photos live in static/img/ and are copied into the TeamMember.photo field by the seed command,
# so they survive on hosted media storage instead of pointing at someone else's server.
TEAM = [
    ("Shankar Poudel", "Co-founder and CEO", True, "shankar.jpeg",
     "Shankar leads Zencraft and is the person clients call when something matters. He starts every engagement by sitting with the people who will actually use the software, and he will tell you honestly when a smaller build will serve you better."),
    ("Khem Bahadur Lodh", "Co-founder, CTO and Software Engineer", True, "khem.jpeg",
     "Khem designs the systems behind our work and still writes code on every project. He keeps releases boring: reviewed by a second engineer, covered by tests and safe to roll back, so your platform stays up while it keeps growing."),
    ("Birendra Kumar Chaudhary", "Co-founder and CPO", True, "birendra.jpeg",
     "Birendra turns business goals into a product plan you can hold us to, with a clear scope, schedule and first release. He tests every design with real users, including people opening a digital service for the first time."),
]

GALLERY = [
    (U("photo-1522071820081-009f0129c71c", 1200, 900), "Sprint planning in the Tilottama office", "team"),
    (U("photo-1497366216548-37526070297c", 1200, 900), "Our main engineering floor", "office"),
    (U("photo-1528605248644-14dd04022da1", 1200, 900), "Friday learning session", "events"),
    (U("photo-1600880292203-757bb62b4baf", 1200, 900), "Client workshop", "team"),
    (U("photo-1531482615713-2afd69097998", 1200, 900), "Pairing on a release", "team"),
    (U("photo-1517048676732-d65bc937f952", 1200, 900), "Architecture review", "events"),
    (U("photo-1556761175-5973dc0f32e7", 1200, 900), "Quarterly all-hands", "events"),
    (U("photo-1504384308090-c894fdcc538d", 1200, 900), "Quiet focus area", "office"),
]

BLOG_CATEGORIES = [("Product and strategy", "product-strategy")]

BLOG_POSTS = [
    dict(slug="fixed-price-vs-dedicated-team", title="Fixed price or dedicated team? How to choose an engagement model", category="product-strategy", author="Shankar Poudel",
         image=U("photo-1552664730-d307ca884978", 1400, 875), tags="engagement models, budgeting, outsourcing",
         excerpt="Both models work well in the right situation and fail badly in the wrong one. A practical checklist for deciding before you sign.",
         body="""<p>Most failed outsourcing projects did not fail because of bad engineers. They failed because the contract model did not match how certain the scope really was.</p>
<h2>When fixed price works</h2>
<p>Fixed price suits projects where you can describe what done looks like before work starts. A company website, a well-understood integration or an MVP after a proper discovery workshop are good candidates.</p>
<ul><li>The feature list fits on two pages and rarely changes.</li><li>You need budget approval for a single number.</li><li>You have limited time to manage a team week to week.</li></ul>
<h2>When a dedicated team works</h2>
<p>Products that learn from users change direction. Writing change requests for every adjustment wastes everyone's time. A dedicated team lets you reprioritise every sprint while paying a predictable monthly cost.</p>
<ul><li>You have a roadmap longer than six months.</li><li>You want the same people to build up knowledge of your domain.</li><li>You have a product owner who can guide the team.</li></ul>
<h2>The hybrid most clients choose</h2>
<p>In practice, many of our clients start with a fixed-price discovery and first release, then move to a dedicated team once the product is live. That combines budget certainty early with flexibility later.</p>
<p>If you are unsure, our project estimator asks the questions that usually decide it, and a 30-minute call is free.</p>"""),
]
