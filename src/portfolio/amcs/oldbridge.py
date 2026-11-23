import re
from urllib.parse import urljoin

from ..base import Disclosure, parse_period

AMC = "Old Bridge Mutual Fund"
SLUG = "oldbridge"
PAGE = "https://www.oldbridgemf.com/statutory-disclosures.html"
ITEM = re.compile(r'<h2[^>]*>([^<]*)</h2>\s*<a href="([^"]+\.xlsx?)"', re.I)


def list_disclosures(session):
    r = session.get(PAGE, timeout=120)
    r.raise_for_status()
    seen = set()
    for label, href in ITEM.findall(r.text):
        label = " ".join(label.split())
        # Half-yearly portfolios share the same month labels; some monthly files omit "portfolio" from the name
        named = label.startswith("Old Bridge") and "Fund" in label
        if not (named or re.search(r"portfolio", href, re.I)) or re.search(r"half|hy_|overlap|dashboard|assets", href, re.I):
            continue
        url = urljoin(PAGE, href)
        period = parse_period(label)
        if period and url not in seen:
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url, scheme=label)
