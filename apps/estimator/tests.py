import json
from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.models import SiteSettings
from apps.core.testing import NOOP_SCAN, make_estimator_catalog, pdf_upload
from apps.estimator import engine
from apps.estimator.models import EstimatorConfig, EstimatorEvent, ProjectInquiry


def answers(**overrides):
    data = {
        "project_type": "web-app", "features": ["auth"], "platforms": ["web"], "timeline": "standard",
        "team_preference": "unsure", "design_needs": "existing", "session_id": "sess-1",
    }
    data.update(overrides)
    return data


class EngineTests(TestCase):
    """Default EstimatorConfig: Rs. 2,150/h blended, 12% contingency, range x0.85 to x1.35, 30 h/week per FTE."""

    def setUp(self):
        make_estimator_catalog()

    def calc(self, **overrides):
        a = answers(**overrides)
        return engine.calculate(a["project_type"], a["features"], a["platforms"], a["timeline"], a["team_preference"], a["design_needs"])

    def test_baseline_math(self):
        result = self.calc()
        # 100 base + 20 auth = 120 h; 120 x 2150 x 1.12 = 288,960
        self.assertEqual(result["hours"], 120)
        self.assertEqual(result["low"], Decimal("250000"))   # 245,616 rounded to nearest 10,000
        self.assertEqual(result["high"], Decimal("390000"))  # 390,096 rounded to nearest 10,000
        # Team under 450 h is 1.75 FTE -> 52.5 h/week -> 2.29 weeks
        self.assertEqual((result["weeks_low"], result["weeks_high"]), (2, 3))
        self.assertEqual([m["role"] for m in result["team"]], ["Full-stack developer", "QA engineer", "Project manager"])
        self.assertIn("indicative", result["disclaimer"])

    def test_extra_platforms_add_their_coefficient(self):
        self.assertEqual(self.calc(platforms=["web", "ios"])["hours"], 158)  # 120 x (1 + 0.32)
        self.assertEqual(self.calc(platforms=["web", "ios", "android"])["hours"], 192)  # 120 x (1 + 0.32 + 0.28)

    def test_invalid_platforms_fall_back_to_web(self):
        result = self.calc(platforms=["playstation", "fridge"])
        self.assertEqual((result["platforms"], result["hours"]), (["web"], 120))

    def test_design_urgency_and_team_multipliers(self):
        result = self.calc(design_needs="uiux", timeline="fast", team_preference="dedicated")
        self.assertEqual(result["hours"], 165)  # 120 x 1.18 x 1.22 x 0.96 = 165.84
        self.assertIn("UI/UX designer", [m["role"] for m in result["team"]])

    def test_multipliers_are_read_from_config(self):
        config = EstimatorConfig.load()
        config.blended_hourly_rate_npr = Decimal("1000")
        config.contingency_pct = Decimal("0")
        config.range_low_factor = Decimal("1")
        config.range_high_factor = Decimal("1")
        config.urgency_multipliers = {"flexible": 1, "standard": 2, "fast": 3, "critical": 4}
        config.save()
        result = self.calc()
        self.assertEqual(result["hours"], 240)
        self.assertEqual((result["low"], result["high"]), (Decimal("240000"), Decimal("240000")))

    def test_minimum_project_value_floor(self):
        config = EstimatorConfig.load()
        config.minimum_project_npr = Decimal("1000000")
        config.save()
        result = self.calc()
        self.assertEqual((result["low"], result["high"]), (Decimal("850000"), Decimal("1350000")))

    def test_only_active_features_of_the_selected_type_count(self):
        result = self.calc(features=["auth", "offline", "hidden", "nonexistent"])
        self.assertEqual((result["features"], result["hours"]), (["auth"], 120))
        mobile = self.calc(project_type="mobile-app", features=["auth", "offline"], platforms=["android"])
        self.assertEqual(mobile["hours"], 270)

    def test_unknown_or_inactive_project_type_raises(self):
        for key in ("nope", "retired"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.calc(project_type=key)

    def test_team_shape_by_size_and_needs(self):
        team, fte = engine.suggest_team(500, ["ios"], "branding", "critical")
        roles = [m["role"] for m in team]
        self.assertEqual(roles, ["Senior developer", "Developer", "QA engineer", "Project manager", "Mobile developer", "UI/UX designer", "Additional developer"])
        self.assertEqual(fte, 6.0)
        team, fte = engine.suggest_team(2000, ["windows"], "existing", "standard")
        self.assertIn("Tech lead", [m["role"] for m in team])
        self.assertIn("Desktop developer", [m["role"] for m in team])
        self.assertEqual(fte, 8.0)
        team, _ = engine.suggest_team(5000, ["web"], "existing", "flexible")
        self.assertEqual(team[0]["role"], "Solution architect")
        small, _ = engine.suggest_team(100, ["android", "macos"], "uiux", "fast")
        self.assertEqual({m["role"]: m["allocation"] for m in small}["Mobile developer"], 0.5)
        self.assertNotIn("Additional developer", [m["role"] for m in small])


@override_settings(UPLOAD_SCAN_HOOK=NOOP_SCAN)
class EstimatorViewTests(TestCase):
    def setUp(self):
        cache.clear()
        make_estimator_catalog()

    def tearDown(self):
        for lead in ProjectInquiry.objects.exclude(document=""):
            lead.document.delete(save=False)

    def submit(self, answer_data=None, **fields):
        data = {"answers": json.dumps(answer_data or answers()), "name": "Ramesh Koirala", "email": "ramesh@example.com",
                "company": "Koirala Traders", "consent": "on"}
        data.update(fields)
        return self.client.post(reverse("estimator:submit_api"), data, HTTP_X_REQUESTED_WITH="fetch")

    def test_start_page_renders(self):
        self.assertContains(self.client.get(reverse("estimator:start")), "What are you building?")

    def test_config_api_lists_active_types_and_features(self):
        data = self.client.get(reverse("estimator:config_api")).json()
        self.assertEqual([t["key"] for t in data["project_types"]], ["web-app", "mobile-app"])
        web = data["project_types"][0]
        self.assertEqual([f["key"] for f in web["features"]], ["auth", "payments"])

    def test_preview_returns_formatted_range(self):
        response = self.client.post(reverse("estimator:preview_api"), json.dumps(answers()), content_type="application/json")
        est = response.json()["estimate"]
        self.assertEqual((est["low_npr"], est["high_npr"]), (250000, 390000))
        self.assertEqual(est["low_npr_display"], "Rs. 2,50,000")
        rate = SiteSettings.load().exchange_rate_npr_per_usd
        self.assertEqual(est["low_usd"], int((Decimal(250000) / rate).quantize(Decimal("1"))))

    def test_preview_rejects_bad_input(self):
        url = reverse("estimator:preview_api")
        self.assertEqual(self.client.post(url, "{not json", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, json.dumps(answers(project_type="nope")), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_submit_creates_lead_with_private_document(self):
        mail.outbox.clear()
        response = self.submit(answers(platforms=["ios", "android"], timeline="bogus"), document=pdf_upload("Brief v2.pdf"),
                               budget_band="5-15l", description="Need a loyalty app")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        lead = ProjectInquiry.objects.get(reference=body["reference"])
        self.assertEqual((lead.project_type_label, lead.platforms, lead.features), ("Web application", ["ios", "android"], ["auth"]))
        self.assertEqual(lead.timeline, "standard")  # unknown values fall back safely
        self.assertEqual((lead.budget_band, lead.status, lead.consent), ("5-15l", "new", True))
        self.assertEqual(lead.exchange_rate, SiteSettings.load().exchange_rate_npr_per_usd)
        self.assertEqual(lead.estimate_low_npr, Decimal(body["estimate"]["low_npr"]))
        self.assertTrue(lead.document.name.startswith("inquiries/"))
        self.assertNotIn("Brief", lead.document.name)
        self.assertEqual(lead.document_name, "Brief v2.pdf")
        with self.assertRaises(ValueError):
            lead.document.url
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(lead.reference, mail.outbox[0].subject)
        self.assertTrue(EstimatorEvent.objects.filter(session_id="sess-1", step=8).exists())
        self.assertEqual(lead.feature_labels, ["Login"])
        self.assertEqual(lead.platform_labels, ["iOS", "Android"])

    def test_submit_validation_errors(self):
        cases = {
            "document": {"document": pdf_upload(content=b"MZ not a pdf")},
            "consent": {"consent": ""},
            "website": {"website": "http://spam"},
            "email": {"email": "not-an-email"},
        }
        for field, extra in cases.items():
            with self.subTest(field=field):
                response = self.submit(**extra)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json()["errors"])
        self.assertEqual(self.submit(answer_data={"project_type": "nope"}).status_code, 400)
        bad = self.client.post(reverse("estimator:submit_api"), {"answers": "{broken", "consent": "on"})
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(ProjectInquiry.objects.exists())

    def test_event_api(self):
        url = reverse("estimator:event_api")
        for _ in range(2):
            self.assertEqual(self.client.post(url, json.dumps({"step": 3, "session_id": "s-9"}), content_type="application/json").status_code, 200)
        self.client.post(url, json.dumps({"step": 99, "session_id": "s-9"}), content_type="application/json")
        self.client.post(url, json.dumps({"step": 2, "session_id": ""}), content_type="application/json")
        self.assertEqual(list(EstimatorEvent.objects.values_list("session_id", "step")), [("s-9", 3)])
        self.assertEqual(self.client.post(url, "nope", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_submit_is_rate_limited(self):
        for _ in range(6):
            self.submit(consent="")
        response = self.submit()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many", response.json()["error"])
