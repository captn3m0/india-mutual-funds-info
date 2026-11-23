import re

from ..base import Disclosure, parse_period

AMC = "Franklin Templeton Mutual Fund"
SLUG = "franklin"
BASE = "https://www.franklintempletonindia.com"


def list_disclosures(session):
    data = session.get(f"{BASE}/api/literature/v1/responseLitJson?type=report", timeout=120).json()
    seen = set()

    def walk(o):
        if isinstance(o, dict):
            if "literatureHref" in o:
                yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    for o in walk(data):
        if o.get("id") != "MONTHLY-PORTFOLIO-DSCLR":
            continue
        period = parse_period(re.sub(r"\(.*", "", o["dctermsTitle"]))
        # a few months are published twice; keep one
        if period and period not in seen:
            seen.add(period)
            yield Disclosure(amc=SLUG, period=period, url=f"{BASE}/download{o['literatureHref']}")
