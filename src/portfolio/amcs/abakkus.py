import json
import re

from ..base import Disclosure, month_end, parse_date, parse_period

AMC = "Abakkus Mutual Fund"
SLUG = "abakkus"
BASE = "https://www.abakkusmf.com"


def list_disclosures(session):
    page = session.get(f"{BASE}/statutory-disclosures.html", timeout=120).text
    data = json.loads(re.search(r'id="verticals-data"[^>]*>(.*?)</script>', page, re.S).group(1))
    seen = set()
    for vertical in data:
        if vertical["title"] not in ("Monthly Portfolio Disclosures", "Monthly Portfolio Disclosure"):
            continue
        for sec in vertical["sections"]:
            for sub in sec.get("subSections", []):
                for item in sub.get("items", []):
                    url = item.get("downloadUrl") or (item.get("downloadMedia") or {}).get("url")
                    period = parse_period(item["title"])
                    day = parse_date(item["title"])
                    if day and day != month_end(period):
                        continue
                    if url and period and url not in seen:
                        seen.add(url)
                        yield Disclosure(amc=SLUG, period=period, url=BASE + url if url.startswith("/") else url)
