from ..base import Disclosure, parse_date, parse_period

AMC = "Trust Mutual Fund"
SLUG = "trust"
API = "https://www.trustmf.com/api/api/Trust/GetData"
QUERY = {
    "systemQueryFileName": "disclosuresweb.xml",
    "tagName": "GetDisclosureByType",
    "searchField": "",
    "searchValue": "",
    "sortField": "uploaddate",
    "sortDirection": "DESC",
    "replaceField": "_slug_",
    "replaceValue": "portfolio-monthly-disclosure",
}


def list_disclosures(session):
    r = session.post(API, json=QUERY, timeout=60)
    r.raise_for_status()
    seen = set()
    for row in r.json().get("resultSetArray") or []:
        url = row.get("fileurl")
        d = parse_date(row.get("title", ""))
        period = f"{d.year:04d}-{d.month:02d}" if d else parse_period(row.get("title", ""))
        if url and period and url not in seen:
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url)
