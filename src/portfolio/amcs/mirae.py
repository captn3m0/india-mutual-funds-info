import re
from urllib.parse import urljoin

from ..base import Disclosure, parse_period
from ..parse import parse_file

AMC = "Mirae Asset Mutual Fund"
SLUG = "mirae"
SITE = "https://www.miraeassetmf.co.in"
API = SITE + "/AjaxService/GetDownloadsData"


def list_disclosures(session):
    body = {"request": {"modulename": "portfolio_tab1", "pgno": 1, "pgsize": 10000}}
    r = session.post(API, json=body, timeout=120)
    r.raise_for_status()
    seen, names = set(), set()
    for item in r.json()["Data"]:
        url = urljoin(SITE, item["URL"].strip())
        path = url.split("?")[0]
        if not re.search(r"\.xlsx?$", path, re.I) or url in seen:
            continue
        seen.add(url)
        head, _, scheme = item["Title"].partition(" for ")
        period = parse_period(head)
        if not period:
            continue
        name = path.rsplit("/", 1)[-1]
        if (period, name) in names:
            name = f"{len(names)}_{name}"
        names.add((period, name))
        yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=" ".join(scheme.split()))


def parse(path, amc="", period=""):
    out = parse_file(path, amc=amc, period=period)
    groups = {}
    for h in out:
        groups.setdefault((h.source, h.sheet), []).append(h)
    # Fund-of-fund sheets holding ~100% in one line escape the fraction heuristic
    for hs in groups.values():
        pcts = [h.pct_nav or 0 for h in hs]
        if 0.97 <= sum(pcts) <= 1.03 and max(map(abs, pcts)) <= 1.05:
            for h in hs:
                if h.pct_nav is not None:
                    h.pct_nav = round(h.pct_nav * 100, 6)
    return out
