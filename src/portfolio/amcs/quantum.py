import datetime
import time

from ..base import Disclosure, links, parse_period

AMC = "Quantum Mutual Fund"
SLUG = "quantum"
PAGE = "https://www.quantumamc.com/portfolio/combined/-1/1/{year}/0"


def list_disclosures(session):
    seen = set()
    for year in range(datetime.date.today().year, 2010, -1):
        r = session.get(PAGE.format(year=year), timeout=60)
        r.raise_for_status()
        for url, label in links(r.text, PAGE):
            if "/FileCDN/" not in url or "All Funds" not in label or url in seen:
                continue
            seen.add(url)
            period = parse_period(label)
            if period:
                yield Disclosure(amc=SLUG, period=period, url=url)
        time.sleep(0.5)
