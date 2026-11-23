import re

from ..base import Disclosure, parse_date, parse_period

AMC = "Aditya Birla Sun Life Mutual Fund"
SLUG = "absl"
BASE = "https://mutualfund.adityabirlacapital.com"
API = BASE + "/postlogin/CustomApi/Resources/FactsheetAccordionById"
ACCORDION = "3ccab227-9de5-4494-b78d-2b4f7c0c054a"
CTYPE = "/sitecore/content/Root/BSL/Library/Lists/FAQ/Customer Types/Individual"


def list_disclosures(session):
    r = session.get(
        API,
        params={"id": ACCORDION, "ctype": CTYPE, "month": " ", "year": 0},
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=120,
    )
    r.raise_for_status()
    seen = set()
    for item in r.json()["AccordionList"]:
        title, url = item["ResourceLink"], item["pdfUrl"]
        # Skip the off-cycle open-ended debt and FoF updates
        if not title.startswith("Monthly Portfolio") or url in seen:
            continue
        seen.add(url)
        # The azureedge CDN host is retired; the same paths are served from the main site
        url = url.replace("https://abcscprod.azureedge.net", BASE)
        title = re.sub(r"(?i)janaury", "January", title)
        d = parse_date(title)
        period = f"{d.year}-{d.month:02d}" if d else parse_period(title)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)
