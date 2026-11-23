import json
import re
import time

from ..base import Disclosure, is_sheet, links, parse_period

AMC = "Canara Robeco Mutual Fund"
SLUG = "canararobeco"
IMPERSONATE = "chrome"
PAGE = "https://www.canararobeco.com/documents/statutory-disclosures/scheme-dashboard/scheme-monthly-portfolio/"


def page(session, year, month, n):
    params = {"filteryear": year, "filtermonth": month}
    if n > 1:
        params["pagination"] = n
    for attempt in range(3):
        r = session.get(PAGE, params=params, timeout=60)
        if r.status_code == 200:
            return r.text
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()


def list_disclosures(session):
    html = session.get(PAGE, timeout=60).text
    by_year = json.loads(re.search(r"monthsByYear\s*=\s*(\{.*?\});", html).group(1))
    for year in sorted(by_year, reverse=True):
        for month in sorted(by_year[year], reverse=True):
            seen = set()
            n = 1
            while True:
                time.sleep(0.3)
                found = 0
                for url, label in links(page(session, year, month, n), PAGE):
                    if "/uploads/" not in url or not is_sheet(url) or url in seen or label == "Download":
                        continue
                    seen.add(url)
                    found += 1
                    period = parse_period(label) or f"{year}-{month}"
                    yield Disclosure(amc=SLUG, period=period, url=url, scheme=label)
                if found < 10 or n >= 20:
                    break
                n += 1
