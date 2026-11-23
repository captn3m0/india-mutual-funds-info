import re

from ..base import Disclosure, parse_period

AMC = "Angel One Mutual Fund"
SLUG = "angelone"
INDEX = "https://www.angelonemf.com/downloads"
FILE = re.compile(r"https://[^\"'\s<>\\]*?/(monthly[-_ ]portfolio[^\"'\s<>\\/]*\.xlsx?)", re.I)


def list_disclosures(session):
    html = session.get(INDEX, timeout=120).text
    best = {}
    for m in FILE.finditer(html):
        url, name = m.group(0), m.group(1)
        stem = re.sub(r"(?i)^monthly[-_ ]portfolio[-_ ]|\.xlsx?$", "", name)
        stem = re.sub(r"(?i)([a-z])(20\d\d)", r"\1-\2", stem)
        period = parse_period(stem)
        if not period:
            continue
        scheme = re.sub(r"^[A-Za-z]+[-_ ]*20\d\d[-_ ]*|[-_ ]\d+$", "", stem).replace("-", " ")
        key = (period, re.sub(r"[^a-z0-9]", "", scheme.lower()))
        # Re-uploads (-1, -2 suffixes) are identical; prefer the one the page links to
        linked = f'href="{url}"' in html
        if key not in best or (linked and not best[key][1]):
            best[key] = (Disclosure(amc=SLUG, period=period, url=url, scheme=scheme), linked)
    for d, _ in best.values():
        yield d
