from ..base import Disclosure, is_sheet, links, parse_period

AMC = "PPFAS Mutual Fund"
SLUG = "ppfas"
INDEX = "https://amc.ppfas.com/downloads/portfolio-disclosure/"


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen = set()
    for url, label in links(html, INDEX):
        name = url.split("?")[0].rsplit("/", 1)[-1]
        # Per-scheme files (PPLF_PPFAS_...) duplicate the consolidated workbook
        if not is_sheet(url) or name in seen or "_PPFAS_" in name:
            continue
        seen.add(name)
        period = parse_period(name) or parse_period(label)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)
