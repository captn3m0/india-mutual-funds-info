import re

from ..base import Disclosure, is_sheet, links, parse_period

AMC = "Helios Mutual Fund"
SLUG = "helios"
IMPERSONATE = "chrome"
INDEX = "https://www.heliosmf.in/portfolio-disclosure"
LABEL = re.compile(r'href="([^"]+)"[^>]*?aria-label="Portfolio Disclosures, Monthly Portfolio, ([^"]*?) download ', re.S)


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen = set()
    for href, scheme in LABEL.findall(html):
        url = links(f'<a href="{href}">x</a>', INDEX)[0][0]
        name = url.split("?")[0].rsplit("/", 1)[-1]
        period = parse_period(name)
        if is_sheet(url) and period and url not in seen:
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url, scheme=scheme)
