import re

from ..base import Disclosure, links, parse_period

AMC = "HSBC Mutual Fund"
SLUG = "hsbc"
INDEX = "https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library"
DATE_TAIL = re.compile(r"\s*(as on\s*)?\d{1,2}\s+[A-Za-z]+\s+\d{4}.*$|\s+-\s+[A-Za-z]+\s+\d{4}.*$", re.I)


def list_disclosures(session):
    html = session.get(INDEX, timeout=120).text
    seen = set()
    for url, label in links(html, INDEX):
        if "/mutual-funds/portfolios/" not in url.lower() or url in seen:
            continue
        seen.add(url)
        # Fortnightly debt files live in this folder too; they are not monthly disclosures
        if re.search(r"fortnight|weekly|half[\s-]*yearly.*debt", label, re.I):
            continue
        period = parse_period(label)
        if not period:
            continue
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        if not re.search(r"\.(xlsx?|zip)$", name, re.I):
            name += ".xlsx"
        consolidated = re.match(r"(?i)(half[\s-]*yearly.*|monthly.*)(portfolio|portfolios)\b", label)
        scheme = "" if consolidated else DATE_TAIL.sub("", label).strip()
        yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=scheme)
