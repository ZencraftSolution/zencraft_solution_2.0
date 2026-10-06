# Content to replace before launch

Every item below is placeholder content written to build and demonstrate the site. None of it
describes work Zencraft Solution has actually done. **Published as it stands, this is a site that
makes claims about clients and results that did not happen** — which is a legal and reputational
problem long before it is an SEO one, and Google's own guidance on reviews and testimonials treats
invented ones as spam.

Nothing here has been changed for you: these are business decisions, and the right people to make
them are the three of you.

Everything is editable in **HQ** (the staff dashboard) unless a file is named.

---

## 1. Blocking: claims about clients and results

### Case studies — HQ → Portfolio → Case studies

All seven are invented, including the client names, the numbers and the quotes attached to them.

| Case study | Invented client | Headline claim |
| --- | --- | --- |
| `mobile-banking-development-bank` | "A class B development bank" | 412k active app users, 38% of branch visits moved online |
| `hospital-information-system` | "A 300-bed teaching hospital in Kathmandu Valley" | 63% shorter OPD wait |
| `omnichannel-fashion-retail` | "Kathmandu Kapda House" | 3.1x online revenue in 6 months |
| `fleet-tracking-logistics` | "Trishuli Cargo Services" | 180 trucks, 18% lower fuel cost per km |
| `university-learning-platform` | "A university affiliate network of 22 colleges" | 46,000 students onboarded |
| `hotel-group-cloud-support` | "Annapurna Heritage Hotels" | 41% lower infrastructure cost |
| `ngo-program-analytics` | "An international development NGO" | 9 country offices on one warehouse |

- [ ] Delete every case study you cannot evidence.
- [ ] Replace with real projects, including the client's written permission to name them. An
      anonymised case study ("a 40-bed private hospital in Butwal") is fine and still sells;
      an invented one is not.
- [ ] Each one needs a real cover image. The current ones are stock photos from Unsplash.

### Testimonials — HQ → Portfolio → Testimonials

All six are invented, with invented people attached to the invented clients above.

| Name | Role | Company |
| --- | --- | --- |
| Sushma Karki | Chief Digital Officer | A class B development bank |
| Dr. Anil Shrestha | Medical Director | Teaching hospital, Kathmandu |
| Pratik Maharjan | Head of E-commerce | Kathmandu Kapda House |
| Nirajan Thapa | Operations Director | Trishuli Cargo Services |
| Aarati Gurung | General Manager | Annapurna Heritage Hotels |
| Rebecca Lindqvist | Regional Operations Lead | International development NGO |

- [ ] Delete all six.
- [ ] Add only quotes a real client actually wrote, with their approval to publish name and company.

---

## 2. Blocking: numbers on the home and about pages

Set in **HQ → Site settings**. The current figures were scaled to look plausible for a company
starting in 2026; they are still guesses.

| Figure | Currently shows | Replace with |
| --- | --- | --- |
| Projects delivered | 14 | the real count |
| Clients served | 9 | the real count |
| People on the team | 11 | the real count (the About page lists 3) |
| Uptime | 99.90% | a figure you measure, or remove the claim |
| Years in business | 1 | correct from your registration date |

- [ ] **The team count contradicts the About page**, which shows three people. Fix one or the other.
- [ ] Only publish an uptime figure if something actually measures it. If nothing does, remove it.

---

## 3. Blocking: claims in copy

| Where | Claim | Note |
| --- | --- | --- |
| `templates/core/home.html` | "Changes reviewed before release 100%" | True only if it is your actual practice |
| `templates/core/home.html` | "Clients in Nepal and abroad" | Only once you have a client abroad |
| `templates/partials/footer.html` | "working with clients across Nepal, Europe, Australia and North America" | Almost certainly not true yet |
| `templates/core/about.html` | "Founded in Rupandehi in 2026" | Check against your registration date |
| `templates/commerce/pricing.html` | "Based on the projects we have delivered so far" | Only with real projects behind the ranges |
| Blog post `how-we-hire-junior-engineers` | "Several of our engineers joined as interns" | Only if true |
| Blog posts (all six) | Entirely written as placeholder content | Rewrite or unpublish |

---

## 4. Blocking: the rate card and prices

**HQ → Commercial → Rate card, Fixed-price ranges, Productized services**

Every rate, range and store price is invented. A visitor can buy a productized service with real
money at these prices today.

- [ ] Confirm or replace every hourly and monthly rate.
- [ ] Confirm or replace every fixed-price range.
- [ ] Confirm or replace every store product's price, and that you can deliver each one.
- [ ] Check the bank details on `templates/commerce/order_done.html`: account name, number and
      SWIFT are placeholders. **Money sent to these does not reach you.**
- [ ] Check the exchange rate in HQ → Site settings (currently Rs. 134.25 per USD).

---

## 5. Important: jobs

**HQ → Recruitment → Job openings**

All seven roles, their salary ranges and their descriptions are invented. Each is published as a
Google JobPosting, so they can appear in Google Jobs and attract real applications.

- [ ] Unpublish every role you are not actually hiring for.
- [ ] Check the salary range on any you keep. It is published to the world.

---

## 6. Important: images

- [ ] **Team photos** are real (yours). Everything else is stock.
- [ ] Case study covers, blog hero images, industry images and the office gallery are Unsplash
      photos. Replace with your own, or keep them and accept that they are generic stock.
- [ ] **Sharing image**: HQ → Site settings has no default sharing image, so shared links fall back
      to the logo, which is not the right shape. Upload a 1200×630 card.
- [ ] Technology logos are loaded from a CDN and are fine.

---

## 7. Check before launch

- [ ] `info@zencraftsolution.com` and `+977 9857055518` — do both work?
- [ ] `careers@zencraftsolution.com` (HQ → Site settings) and the `hello@zencraftsolution.com`
      hard-coded in `templates/500.html` — do these exist?
- [ ] Office hours "Sun to Fri, 9:30 to 18:00 NPT".
- [ ] The address "Tilottama Municipality-3, Rupandehi, Nepal" is published in your structured
      data, so Google will treat it as your business location.
- [ ] The four social links in the footer point at live accounts.
- [ ] Privacy policy and terms: both have been corrected to match what the code does, but a
      lawyer should read them before you trade under them.

---

## How to check you have finished

```
python manage.py shell -c "
from apps.portfolio.models import CaseStudy, Testimonial
print('case studies:', CaseStudy.objects.count())
print('testimonials:', Testimonial.objects.count())
"
```

Anything still carrying a name from the tables above is still placeholder content.
