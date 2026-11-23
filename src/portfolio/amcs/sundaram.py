import re

from ..base import Disclosure, parse_period

AMC = "Sundaram Mutual Fund"
SLUG = "sundaram"
BASE = "https://www.sundarammutual.com"
API = BASE + "/ajax/Modules_Disclosure_Monthly_Fortnightly_Adhoc_Portfolios,App_Web_00rybqzs.ashx"
LINK = re.compile(r"href=\\?'([^'\\]+)\\?'[^>]*>(?:<i[^>]*></i>)?([^<]+)</a>")


def list_disclosures(session):
    r = session.post(f"{API}?_method=GetCategory&_session=no", data={"Catid": "Monthly"}, timeout=120)
    seen = set()
    for href, label in LINK.findall(r.text):
        period = parse_period(label)
        if period and href not in seen and re.search(r"\.xlsx?$", href, re.I):
            seen.add(href)
            yield Disclosure(amc=SLUG, period=period, url=BASE + href, scheme=label.split(" - ")[0].replace("Monthly Portfolio Disclosure", "").strip())
