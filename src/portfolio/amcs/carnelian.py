import re
from html import unescape
from urllib.parse import urljoin

from ..base import Disclosure, parse_period

AMC = "Carnelian Mutual Fund"
SLUG = "carnelian"
INDEX = "https://carnelianmf.com/statutory-disclosures"
ITEM = re.compile(r'\\"url\\":\\"([^"\\]*Monthly[^"\\]*)\\".{0,300}?\\"name\\":\\"([^"\\]*)\\"', re.S)


def list_disclosures(session):
    html = unescape(session.get(INDEX, timeout=60).text)
    seen = set()
    for path, name in ITEM.findall(html):
        period = parse_period(name)
        url = urljoin(INDEX, path)
        if period and url not in seen and re.search(r"monthly[_ ]portfolio", name, re.I):
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url, filename=f"{name}.xlsx")
