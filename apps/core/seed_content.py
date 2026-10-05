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
    dict(
        slug="hospital-information-system", title="A hospital information system that cut OPD waiting time by 63%",
        client="A 300-bed teaching hospital in Kathmandu Valley", anonymized=True, industry="healthcare", services=["custom-software-development", "data-analytics", "help-desk-services"],
        techs=["dotnet", "wpf", "postgresql", "python", "metabase"], year=2026, duration="6 months", team=7, featured=True,
        cover=U("photo-1519494026892-80bbd2d6fd0d", 1600, 1000),
        summary="Registration, OPD, pharmacy, lab and billing unified in one desktop and web system across 14 departments.",
        challenge="Patients registered separately at each counter, lab results were delivered on paper and billing was reconciled by hand every night. Queues at the OPD often exceeded an hour, and doctors could not see a patient's history from previous visits.",
        solution="We built a modular hospital information system with a fast WPF desktop client for high-volume counters and a web interface for doctors and management. Lab analysers were integrated over HL7 so results flow directly into patient records.\n\nA token system with SMS updates replaced the physical queue, and a data warehouse now feeds daily dashboards for bed occupancy, revenue and department performance.",
        architecture="WPF desktop clients with local caching, ASP.NET Core APIs, PostgreSQL with streaming replication, HL7 listener service for analysers, Metabase on a nightly-refreshed warehouse.",
        results=[{"value": "63%", "label": "Shorter average OPD wait"}, {"value": "1.2M", "label": "Patient records migrated"}, {"value": "14", "label": "Departments on one system"}, {"value": "0", "label": "Data loss incidents since launch"}],
        code_language="csharp",
        code="""public async Task HandleResultAsync(HL7Message message, CancellationToken ct)
{
    var sampleId = message.Get("OBR-3");
    var order = await _orders.FindBySampleAsync(sampleId, ct)
        ?? throw new UnmatchedSampleException(sampleId);

    foreach (var obx in message.Segments("OBX"))
    {
        order.AddResult(
            test: obx.Get("OBX-3.1"),
            value: obx.Get("OBX-5"),
            unit: obx.Get("OBX-6"),
            flag: obx.Get("OBX-8"));
    }

    await _orders.SaveAsync(order, ct);
    await _notifier.ResultReadyAsync(order.PatientId, ct);
}""",
    ),
    dict(
        slug="omnichannel-fashion-retail", title="Omnichannel commerce that tripled online revenue for a fashion retailer",
        client="Kathmandu Kapda House", anonymized=False, industry="retail-ecommerce", services=["web-development", "mobile-application-development", "infrastructure-services"],
        techs=["nextjs", "django", "postgresql", "elasticsearch", "aws", "flutter"], year=2026, duration="4 months", team=5, featured=True,
        cover=U("photo-1441984904996-e0b6ba687e04", 1600, 1000),
        summary="A headless storefront, mobile app and inventory sync across 9 stores and 2 warehouses.",
        challenge="Stock shown on the website was often wrong, so customers ordered items that had already sold in a shop. Checkout supported only cash on delivery, and the old site took more than six seconds to load on mobile data.",
        solution="We connected the retailer's POS system to a new inventory service that updates stock across every channel within seconds. A Next.js storefront with image optimisation brought mobile load times under two seconds.\n\nCheckout now supports eSewa, Khalti, Fonepay and cards, and a delivery partner integration prints labels and sends tracking SMS automatically.",
        architecture="Next.js storefront on a CDN, Django commerce API, Elasticsearch for search, event-driven stock sync from POS, AWS with autoscaling for festival sales.",
        results=[{"value": "3.1x", "label": "Online revenue in 6 months"}, {"value": "1.4s", "label": "Median mobile page load"}, {"value": "71%", "label": "Orders paid online, up from 0"}, {"value": "27%", "label": "Repeat purchase rate"}],
        code_language="typescript",
        code="""export async function reserveStock(items: CartItem[], orderId: string) {
  // Reserve across locations, nearest warehouse first, all or nothing
  return db.transaction(async (tx) => {
    for (const item of items) {
      const levels = await tx.stockLevels.forUpdate().bySku(item.sku, { order: 'distance' });
      let needed = item.quantity;
      for (const level of levels) {
        const take = Math.min(level.available, needed);
        if (take > 0) await tx.reservations.create({ orderId, levelId: level.id, quantity: take });
        needed -= take;
        if (needed === 0) break;
      }
      if (needed > 0) throw new OutOfStockError(item.sku);
    }
  });
}""",
    ),
    dict(
        slug="fleet-tracking-logistics", title="Live fleet tracking and dispatch for 180 trucks across Nepal",
        client="Trishuli Cargo Services", anonymized=False, industry="logistics", services=["mobile-application-development", "data-analytics", "infrastructure-services"],
        techs=["kotlin", "nodejs", "kafka", "postgresql", "google-cloud", "grafana"] , year=2026, duration="3 months", team=4, featured=True,
        cover=U("photo-1601584115197-04ecc0da31d7", 1600, 1000),
        summary="GPS tracking, driver apps and a dispatch console that plans routes around real road conditions.",
        challenge="Dispatchers coordinated drivers over phone calls and could not tell customers when a delivery would arrive. Monsoon road closures on the Prithvi and BP highways caused missed deadlines, and proof of delivery was on paper slips that often went missing.",
        solution="We integrated the existing Teltonika GPS devices with a streaming pipeline and built an Android driver app for trip assignments, photos and digital signatures.\n\nThe dispatch console shows every truck live, flags delays, and suggests alternative routes using closure reports. Customers get SMS updates and a tracking link.",
        architecture="Teltonika devices streaming to a Node.js ingestion service, Kafka for position events, PostGIS for geospatial queries, Kotlin driver app with offline queueing.",
        results=[{"value": "18%", "label": "Lower fuel cost per km"}, {"value": "2,300", "label": "Deliveries tracked per day"}, {"value": "11 min", "label": "Faster average dispatch"}, {"value": "96%", "label": "Digital proof of delivery"}],
        code_language="sql",
        code="""-- Trucks within 25 km of a pickup that can arrive before the loading window closes
SELECT t.id, t.plate_number,
       ST_Distance(p.position::geography, :pickup::geography) / 1000 AS km_away
FROM trucks t
JOIN LATERAL (
    SELECT position FROM truck_positions
    WHERE truck_id = t.id ORDER BY recorded_at DESC LIMIT 1
) p ON true
WHERE t.status = 'available'
  AND t.capacity_kg >= :load_kg
  AND ST_DWithin(p.position::geography, :pickup::geography, 25000)
ORDER BY km_away
LIMIT 5;""",
    ),
    dict(
        slug="university-learning-platform", title="A learning platform for 46,000 students that held up on results day",
        client="A university affiliate network of 22 colleges", anonymized=True, industry="education", services=["web-development", "testing-qa", "infrastructure-services"],
        techs=["react", "django", "postgresql", "redis", "aws", "k6"], year=2026, duration="5 months", team=6, featured=True,
        cover=U("photo-1427504494785-3a9ca7044f45", 1600, 1000),
        summary="Courses, assignments, online exams and result publishing for 22 colleges on one platform.",
        challenge="The previous portal crashed every results day and students waited hours to see marks. Colleges used different tools for attendance, assignments and exams, and students outside Kathmandu struggled with heavy video lectures on slow connections.",
        solution="We built a multi-tenant learning platform with adaptive video, offline reading and assignment submission that works on weak connections. Load testing with k6 at five times the previous peak shaped the caching and queueing design.\n\nResults are pre-computed and served from cache, so results day now looks like any other day on the monitoring dashboards.",
        architecture="React front end, Django multi-tenant API, PostgreSQL with read replicas, Redis caching, adaptive HLS video on S3 and CloudFront.",
        results=[{"value": "46,000", "label": "Students onboarded"}, {"value": "92%", "label": "Assignment submission rate"}, {"value": "0.8s", "label": "Result lookup at peak"}, {"value": "22", "label": "Colleges on one platform"}],
        code_language="python",
        code="""def publish_results(exam_id):
    exam = Exam.objects.get(pk=exam_id)
    pipe = redis.pipeline(transaction=False)
    for row in Result.objects.filter(exam=exam).values("symbol_no", "payload").iterator(chunk_size=2000):
        pipe.set(f"result:{exam.code}:{row['symbol_no']}", json.dumps(row["payload"]), ex=60 * 60 * 24 * 30)
    pipe.execute()
    exam.published_at = timezone.now()
    exam.save(update_fields=["published_at"])""",
    ),
    dict(
        slug="hotel-group-cloud-support", title="Cloud migration and 24/7 support for a heritage hotel group",
        client="Annapurna Heritage Hotels", anonymized=False, industry="hospitality", services=["infrastructure-services", "help-desk-services", "application-services"],
        techs=["aws", "terraform", "docker", "nginx", "mysql", "laravel"], year=2026, duration="3 months, then ongoing", team=4, featured=True,
        cover=U("photo-1542314831-068cd1dbfeeb", 1600, 1000),
        summary="Booking engine, property management and back-office systems moved to the cloud with round-the-clock support.",
        challenge="Six properties ran on ageing servers in a single office. A power failure during the autumn trekking season took the booking engine offline for two days, and staff had no reliable way to get IT help at night.",
        solution="We migrated every workload to AWS using Terraform, upgraded the Laravel booking engine to a supported version and set up monitoring with on-call alerts.\n\nOur Gold help desk now covers front-office staff in every property around the clock, and quarterly reviews have removed the most common ticket causes.",
        architecture="Terraform-managed AWS environment across two availability zones, containerised Laravel apps behind Nginx, RDS MySQL with point-in-time recovery, CloudWatch and PagerDuty alerting.",
        results=[{"value": "41%", "label": "Lower infrastructure cost"}, {"value": "14 min", "label": "Median critical response"}, {"value": "0", "label": "Unplanned downtime in peak season"}, {"value": "6", "label": "Properties supported 24/7"}],
        code_language="hcl",
        code="""module "booking_service" {
  source         = "./modules/ecs-service"
  name           = "booking-engine"
  image          = "${var.registry}/booking-engine:${var.release}"
  desired_count  = 2
  cpu            = 512
  memory         = 1024
  subnets        = module.network.private_subnets
  health_path    = "/healthz"

  autoscaling = {
    min_capacity = 2
    max_capacity = 8
    cpu_target   = 60
  }
}""",
    ),
    dict(
        slug="ngo-program-analytics", title="One view of programs and donor reporting across nine country offices",
        client="An international development NGO", anonymized=True, industry="government-ngo", services=["data-analytics", "it-consulting", "custom-software-development"],
        techs=["python", "airflow", "dbt", "postgresql", "metabase", "azure"], year=2026, duration="4 months", team=4, featured=False,
        cover=U("photo-1488521787991-ed7bbaae773c", 1600, 1000),
        summary="Field data collection, a program warehouse and donor dashboards replacing monthly spreadsheet consolidation.",
        challenge="Each country office reported in its own spreadsheet format. Consolidating figures for donors took the regional team six working days every month, and numbers regularly disagreed between reports.",
        solution="We ran a two-week consulting phase to agree common indicators, then built pipelines from KoboToolbox, the finance system and partner uploads into a modelled warehouse.\n\nDonor-specific dashboards now refresh daily, and data quality checks flag missing or inconsistent submissions before they reach a report.",
        architecture="Airflow orchestrating extraction from KoboToolbox and finance APIs, dbt models in Azure PostgreSQL, Metabase dashboards with row-level security per donor.",
        results=[{"value": "9", "label": "Country offices on one warehouse"}, {"value": "4 h", "label": "Monthly reporting, down from 6 days"}, {"value": "31", "label": "Shared program indicators"}, {"value": "100%", "label": "Reports reconciled to finance"}],
        code_language="sql",
        code="""-- models/marts/fct_beneficiaries_reached.sql
select
    o.country_code,
    p.program_code,
    date_trunc('month', s.submitted_at) as month,
    count(distinct s.beneficiary_id) as beneficiaries_reached,
    count(distinct s.beneficiary_id) filter (where b.gender = 'female') as women_reached
from {{ ref('stg_kobo_submissions') }} s
join {{ ref('dim_beneficiaries') }} b using (beneficiary_id)
join {{ ref('dim_programs') }} p using (program_id)
join {{ ref('dim_offices') }} o using (office_id)
where s.is_valid
group by 1, 2, 3""",
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

TEAM = [
    ("Rohan Adhikari", "Co-founder and CEO", True, U("photo-1506794778202-cad84cf45f1d", 600, 750), "Rohan spent eight years building banking software in Singapore before returning to Nepal to start Zencraft in 2026."),
    ("Sabina Rai", "Co-founder and CTO", True, U("photo-1573497019940-1c28c88b4f3e", 600, 750), "Sabina leads architecture and engineering standards. She has designed systems for banks, hospitals and three national-scale platforms."),
    ("Bikash Lama", "Head of Delivery", True, U("photo-1519085360753-af0119f7cbe7", 600, 750), "Bikash runs delivery across 20 active projects and makes sure every client has a plan they can hold us to."),
    ("Pooja Bajracharya", "Head of Design", True, U("photo-1534528741775-53994a69daeb", 600, 750), "Pooja leads product design and research, with a focus on software that works for first-time digital users."),
    ("Suraj K.C.", "Principal Engineer", False, U("photo-1531427186611-ecfd6d936c79", 600, 750), "Backend and distributed systems."),
    ("Anisha Tamang", "QA Lead", False, U("photo-1438761681033-6461ffad8d80", 600, 750), "Test automation and release quality."),
    ("Kiran Poudel", "DevOps Lead", False, U("photo-1472099645785-5658abf4ff4e", 600, 750), "Cloud infrastructure and reliability."),
    ("Meera Joshi", "People and Talent Lead", False, U("photo-1494790108377-be9c29b29330", 600, 750), "Hiring, growth paths and culture."),
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

DEPARTMENTS = [("Engineering", "engineering"), ("Quality assurance", "quality-assurance"), ("Design", "design"), ("Support and operations", "support-operations")]

JOBS = [
    dict(slug="senior-django-developer", title="Senior Django Developer", dept="engineering", mode="hybrid", type="full-time", level="senior", years="5+ years",
         salary=(180000, 260000), techs=["python", "django", "postgresql", "redis", "docker", "aws"],
         summary="Lead backend development on banking and healthcare platforms used by hundreds of thousands of people.",
         description="You will own the design and delivery of backend services for two long-running client platforms. You will make architecture decisions with the CTO, review code, mentor mid-level developers and talk directly with client technical teams.",
         responsibilities="Design and build Django services and REST APIs for high-traffic platforms\nWrite architecture decision records and review designs with the team\nReview pull requests and mentor two to three developers\nImprove performance, observability and test coverage\nJoin client calls to scope features and explain trade-offs",
         requirements="5+ years building production Python applications, 3+ with Django\nStrong PostgreSQL skills including query tuning and migrations\nExperience with Celery or another task queue, and Redis\nComfort with Docker and a major cloud provider\nClear written English for documentation and client communication",
         nice="Experience with payment, banking or healthcare systems\nKubernetes in production\nOpen source contributions",
         growth="Senior Developer to Tech Lead within 18 to 24 months, with a published level framework and six-monthly reviews."),
    dict(slug="flutter-developer", title="Flutter Developer", dept="engineering", mode="hybrid", type="full-time", level="mid", years="2 to 4 years",
         salary=(110000, 170000), techs=["flutter", "kotlin", "swift", "django"],
         summary="Build mobile apps for banking, logistics and retail clients that run well on budget Android phones.",
         description="You will join a mobile squad of four building and maintaining Flutter apps with tens of thousands of daily users. You will work closely with designers and backend developers from sprint planning to store release.",
         responsibilities="Build features in Flutter with clean state management\nWrite widget and integration tests\nProfile and fix performance issues on low-end devices\nManage App Store and Play Store releases\nCollaborate with backend developers on API design",
         requirements="2+ years of professional Flutter development\nAt least one app published to the Play Store or App Store\nUnderstanding of REST APIs, authentication and local storage\nFamiliarity with Bloc, Riverpod or Provider",
         nice="Native Android or iOS experience\nExperience with payment SDKs such as eSewa or Khalti\nCI/CD for mobile using Codemagic or GitHub Actions",
         growth="Mid-level to Senior Mobile Developer within 18 months."),
    dict(slug="junior-qa-engineer", title="Junior QA Engineer", dept="quality-assurance", mode="onsite", type="full-time", level="junior", years="0 to 2 years",
         salary=(50000, 75000), techs=["playwright", "postman", "selenium"],
         summary="Learn manual and automated testing on real client projects with a structured mentoring plan.",
         description="This role is ideal for recent graduates who enjoy finding how things break. You will start with manual and API testing, then move into automation with a senior QA mentor over your first six months.",
         responsibilities="Write and run test cases for web and mobile features\nReport clear, reproducible bugs\nTest APIs with Postman\nLearn and contribute to Playwright automation suites\nTake part in sprint planning and release sign-off",
         requirements="Bachelor's degree in computing, or equivalent practical experience\nBasic understanding of how web applications work\nCareful attention to detail and clear written communication\nWillingness to learn automation",
         nice="Any testing course or certification such as ISTQB Foundation\nBasic JavaScript or Python\nPersonal projects or internships",
         growth="Junior to QA Engineer in 12 months, with a clear path to automation or performance specialisation."),
    dict(slug="devops-engineer", title="DevOps Engineer", dept="engineering", mode="hybrid", type="full-time", level="mid", years="3+ years",
         salary=(150000, 220000), techs=["aws", "terraform", "kubernetes", "docker", "github-actions", "nginx"],
         summary="Automate and run infrastructure for client platforms across AWS, Azure and Nepali data centres.",
         description="You will join a team of three responsible for infrastructure, deployment pipelines and reliability for more than 30 production systems. You will take part in a fair, paid on-call rotation.",
         responsibilities="Build and maintain infrastructure with Terraform\nDesign CI/CD pipelines with automated testing and rollbacks\nSet up monitoring, logging and alerting\nRespond to incidents and write blameless post-mortems\nReview cloud costs and propose savings",
         requirements="3+ years in DevOps, SRE or systems engineering\nHands-on AWS or Azure experience\nTerraform or another infrastructure as code tool\nDocker in production and good Linux fundamentals\nScripting in Bash or Python",
         nice="Kubernetes administration\nAWS or Azure certification\nExperience with local data centre hosting",
         growth="DevOps Engineer to Senior or Platform Lead within 24 months."),
    dict(slug="ui-ux-designer", title="UI/UX Designer", dept="design", mode="hybrid", type="full-time", level="mid", years="3+ years",
         salary=(100000, 160000), techs=[],
         summary="Design products for first-time digital users and demanding enterprise teams alike.",
         description="You will lead design on two to three client projects at a time, from research and workshops through to design systems and developer handover.",
         responsibilities="Run user interviews and usability tests\nCreate user flows, wireframes and high-fidelity designs in Figma\nBuild and maintain component libraries\nFacilitate client workshops with our product lead\nWork closely with developers during implementation",
         requirements="3+ years designing web or mobile products\nA portfolio showing process, not just final screens\nStrong Figma skills including components and auto layout\nUnderstanding of accessibility guidelines",
         nice="Experience designing in Nepali as well as English\nMotion or prototyping skills\nBasic HTML and CSS",
         growth="Designer to Senior Designer in 18 to 24 months."),
    dict(slug="software-engineering-intern", title="Software Engineering Intern", dept="engineering", mode="onsite", type="internship", level="intern", years="Final-year students or recent graduates",
         salary=(20000, 30000), techs=["python", "django", "react", "postgresql"],
         summary="A paid three-month internship with a real project, a mentor and a path to a full-time offer.",
         description="Interns join a project team, not a sandbox. You will ship real features with a dedicated mentor, attend code reviews and present your work at the end of the program. Most of our junior engineers started as interns.",
         responsibilities="Build small features and fix bugs under guidance\nWrite tests for your code\nParticipate in daily stand-ups and code reviews\nDocument what you learn for the next intern cohort",
         requirements="Final-year student or graduate in computing or a related field\nBasic knowledge of one programming language\nA GitHub profile or a project you can walk us through\nAvailability for three months full-time",
         nice="Any Django, React or Flutter projects\nParticipation in hackathons or coding clubs",
         growth="Strong interns receive a Junior Developer offer at the end of the program."),
    dict(slug="it-help-desk-specialist", title="IT Help Desk Specialist", dept="support-operations", mode="onsite", type="full-time", level="junior", years="1+ years",
         salary=(45000, 65000), techs=["azure"],
         summary="Be the first line of support for hotel, bank and school staff who rely on our managed services.",
         description="You will resolve support tickets by phone, email and chat, and escalate complex issues to engineers. Shifts rotate fairly across our 24/7 schedule with a night-shift allowance.",
         responsibilities="Respond to and resolve L1 support tickets within SLA\nReset passwords, manage accounts and troubleshoot devices\nDocument fixes in the knowledge base\nEscalate application issues with clear notes",
         requirements="1+ year in IT support or a related role\nWindows, Microsoft 365 and basic networking knowledge\nFriendly, patient communication in Nepali and English\nWillingness to work rotating shifts",
         nice="CompTIA A+ or Microsoft certifications\nExperience with Freshdesk or Jira Service Management",
         growth="Help Desk to L2 Support or Systems Administrator within 18 months."),
]

BLOG_CATEGORIES = [("Engineering", "engineering"), ("Product and strategy", "product-strategy"), ("Cloud and DevOps", "cloud-devops"), ("Careers and culture", "careers-culture")]

BLOG_POSTS = [
    dict(slug="fixed-price-vs-dedicated-team", title="Fixed price or dedicated team? How to choose an engagement model", category="product-strategy", author="Bikash Lama",
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
    dict(slug="core-web-vitals-nepal-mobile", title="Why your site is slow on Nepali mobile networks, and what to fix first", category="engineering", author="Suraj K.C.",
         image=U("photo-1460925895917-afdab827c52f", 1400, 875), tags="performance, core web vitals, mobile",
         excerpt="Most performance advice assumes fast phones on fast networks. Here is what actually moves the numbers for users on mid-range Android devices.",
         body="""<p>We test every client site on a Rs. 18,000 Android phone over a throttled 4G connection. It changes priorities quickly.</p>
<h2>1. Ship less JavaScript</h2>
<p>Parsing and executing JavaScript is the biggest cost on mid-range phones. Audit third-party scripts first. Chat widgets, heatmaps and multiple analytics tags often add more weight than the site itself.</p>
<h2>2. Serve the right image size</h2>
<p>A 2,400 pixel hero image squeezed into a 390 pixel screen is still downloaded in full. Use <code>srcset</code>, modern formats like WebP or AVIF, and lazy-load anything below the fold.</p>
<h2>3. Cache close to your users</h2>
<p>If your server is in Europe or the US, every request travels a long way. A CDN with points of presence in the region cuts time to first byte dramatically.</p>
<h2>4. Measure real users</h2>
<p>Lab scores are a guide. Real user monitoring shows what customers actually experience, broken down by device and network.</p>
<blockquote>For one retail client, removing two unused tracking scripts improved mobile Largest Contentful Paint by 1.3 seconds.</blockquote>"""),
    dict(slug="legacy-modernization-without-rewrite", title="Modernizing a legacy system without a risky full rewrite", category="engineering", author="Sabina Rai",
         image=U("photo-1504639725590-34d0984388bd", 1400, 875), tags="modernization, legacy, architecture",
         excerpt="The strangler pattern lets you replace an old system one piece at a time while the business keeps running. Here is how we apply it.",
         body="""<p>Full rewrites are tempting. The old code is messy, the framework is unsupported and nobody wants to touch it. Yet rewrites regularly run over time and budget, because the old system contains years of business rules nobody wrote down.</p>
<h2>Put a front door in place</h2>
<p>We start by routing all traffic through a gateway or proxy. At first it simply forwards every request to the legacy system. Nothing changes for users.</p>
<h2>Replace one capability at a time</h2>
<p>Pick a module with high business value and clear boundaries, such as reporting or customer notifications. Build it as a new service, then route only those requests to it. Keep the old path available behind a feature flag.</p>
<h2>Keep data consistent</h2>
<p>The hardest part is usually data. We use change data capture or scheduled synchronisation so old and new systems agree during the transition.</p>
<h2>Retire with evidence</h2>
<p>Once a legacy module receives no traffic for an agreed period, remove it. Over several quarters the old system shrinks until it disappears.</p>"""),
    dict(slug="cloud-costs-five-quick-wins", title="Five quick wins that cut cloud bills by a quarter", category="cloud-devops", author="Kiran Poudel",
         image=U("photo-1451187580459-43490279c0fa", 1400, 875), tags="cloud, cost optimisation, aws",
         excerpt="Cloud spend grows quietly. These five checks take a day and usually save 20 to 30 percent.",
         body="""<p>Cloud providers make it easy to start resources and easy to forget them. These are the checks we run first in every infrastructure review.</p>
<h2>1. Rightsize instances</h2><p>Most servers run at under 20 percent CPU. Look at two weeks of metrics and step down one size where headroom allows.</p>
<h2>2. Delete idle resources</h2><p>Unattached disks, old snapshots, forgotten load balancers and test environments add up every month.</p>
<h2>3. Schedule non-production</h2><p>Development and staging rarely need to run nights and weekends. Scheduling them off saves around 65 percent of their cost.</p>
<h2>4. Commit for steady workloads</h2><p>Reserved instances or savings plans for predictable production workloads cut compute costs significantly.</p>
<h2>5. Watch data transfer</h2><p>Traffic between regions and out to the internet is often the surprise line on the bill. A CDN and keeping services in one region help.</p>"""),
    dict(slug="how-we-hire-junior-engineers", title="How we hire junior engineers, and why we skip trick questions", category="careers-culture", author="Meera Joshi",
         image=U("photo-1522202176988-66273c2fd55f", 1400, 875), tags="hiring, careers, interviews",
         excerpt="Our interview process for junior roles focuses on how people learn and communicate, not on memorised algorithms.",
         body="""<p>Several of our engineers joined as interns or juniors. Hiring well at the entry level is one of the best investments we make.</p>
<h2>You can apply without a polished CV</h2>
<p>Our application form lets you upload a CV or fill in your education, experience and projects directly. A strong project matters more to us than formatting.</p>
<h2>A short, realistic take-home task</h2>
<p>We send a small task that takes two to three hours, based on work we actually do. You can use any resources you would use on the job.</p>
<h2>A conversation about your work</h2>
<p>In the interview, you walk us through your solution. We ask what you would change with more time, and how you would explain it to a non-technical client.</p>
<h2>Feedback for everyone</h2>
<p>Every candidate who completes the task receives written feedback, whether or not we make an offer.</p>"""),
    dict(slug="discovery-workshop-what-to-expect", title="What happens in a discovery workshop, and why it saves money", category="product-strategy", author="Pooja Bajracharya",
         image=U("photo-1531403009284-440f080d1e12", 1400, 875), tags="discovery, product, workshops",
         excerpt="Two days of structured work before development can prevent months of rework. Here is the agenda we follow.",
         body="""<p>Clients sometimes ask why they should pay for a workshop instead of starting development straight away. The answer is simple: changing a sticky note costs nothing, changing shipped code costs a lot.</p>
<h2>Day one: problems and people</h2>
<p>We map the business goals, the users and their current journey. We list assumptions and decide which ones are risky enough to test.</p>
<h2>Day two: solution and scope</h2>
<p>We sketch solutions together, prioritise features into a first release and later phases, and review technical constraints with our architect.</p>
<h2>After the workshop</h2>
<ul><li>A prioritised backlog with acceptance criteria</li><li>A clickable prototype of the key screens</li><li>An architecture outline and risk list</li><li>A fixed-price quote for the first release</li></ul>
<p>If you go ahead within 60 days, the workshop fee is credited against the project.</p>"""),
]
