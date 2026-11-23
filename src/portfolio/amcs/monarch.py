from ..base import Disclosure, is_sheet, links, parse_period

AMC = "Monarch Mutual Fund"
SLUG = "monarch"
PAGE = "https://www.monarchamc.in/forms-downloads/portfolio-holdings/monthly"


def list_disclosures(session):
    r = session.get(PAGE, timeout=60)
    r.raise_for_status()
    seen = set()
    for url, _ in links(r.text, PAGE):
        name = url.rsplit("/", 1)[-1]
        if not is_sheet(url) or not name.startswith("Monthly_Portfolio") or url in seen:
            continue
        seen.add(url)
        period = parse_period(name)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)
