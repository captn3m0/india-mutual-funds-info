import re
import time

from ..base import Disclosure, links, parse_period

AMC = "quant Mutual Fund"
SLUG = "quant"
BASE = "https://quantmutual.com"
API = BASE + "/statutorydisclosures.aspx/displaydisclouser"
PAGE = BASE + "/statutory-disclosures"


def list_disclosures(session):
    html = session.get(PAGE, timeout=60).text
    years = sorted(set(re.findall(r"id='(\d{4})' onclick=\"javascript:submit_event\(this\.id, 'MONTHLY PORTFOLIO'\)", html)))
    seen = set()
    for year in years:
        r = session.post(API, json={"id": year, "cat": "MONTHLY PORTFOLIO"}, timeout=60)
        for url, label in links(r.json()["d"], BASE):
            period = parse_period(label)
            if period and url not in seen:
                seen.add(url)
                yield Disclosure(amc=SLUG, period=period, url=url)
        time.sleep(0.3)
