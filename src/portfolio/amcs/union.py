import re

from ..base import Disclosure, parse_date, parse_period

AMC = "Union Mutual Fund"
SLUG = "union"
PAGE = "https://www.unionmf.com/about-us/downloads/monthly-portfolio"
ITEM = re.compile(r'Title:\s*"([^"]*)",\s*Url:\s*"([^"]+)"')
FOLDER = re.compile(r"/([a-z]+-20\d\d)/[^/]+$")


def list_disclosures(session):
    html = session.get(PAGE, timeout=120).text
    seen = set()
    for title, url in ITEM.findall(html):
        path = url.split("?")[0]
        if not re.search(r"\.xlsx?$", path, re.I):
            continue
        name = path.rsplit("/", 1)[-1]
        d = parse_date(name)
        folder = FOLDER.search(path)
        period = f"{d.year:04d}-{d.month:02d}" if d else parse_period(folder.group(1) if folder else title)
        if period and (period, name) not in seen:
            seen.add((period, name))
            yield Disclosure(amc=SLUG, period=period, url=url, scheme=title)
