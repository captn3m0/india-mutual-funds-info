from ..base import Disclosure, is_sheet, links, parse_period

AMC = "DSP Mutual Fund"
SLUG = "dsp"
INDEX = "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures"


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen = set()
    for url, label in links(html, INDEX):
        if not label.startswith("Portfolio Details") or not is_sheet(url) or url in seen:
            continue
        seen.add(url)
        period = parse_period(label)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)
