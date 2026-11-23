import re
from urllib.parse import unquote

from ..base import Disclosure, is_sheet, links, parse_period

AMC = "ASK MUTUAL FUND"
SLUG = "ask"
INDEX = "https://www.askmutualfund.com/pages/downloads.html"
BASE = "https://www.askmutualfund.com/"


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen = set()
    for url, _ in links(html, BASE):
        name = unquote(url.rsplit("/", 1)[-1])
        if not is_sheet(url) or url in seen or not re.search(r"monthly[_\- ]portfolio", name, re.I):
            continue
        seen.add(url)
        period = parse_period(name)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)
