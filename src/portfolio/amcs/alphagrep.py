from ..base import Disclosure, parse_period

AMC = "AlphaGrep Mutual Fund"
SLUG = "alphagrep"
CMS = "https://cmsweb.alphagrepmf.ai"


def list_disclosures(session):
    page, pages = 1, 1
    while page <= pages:
        r = session.get(
            f"{CMS}/api/portfolios?populate=*&pagination[pageSize]=100&pagination[page]={page}", timeout=120
        ).json()
        pages = r["meta"]["pagination"]["pageCount"]
        page += 1
        for item in r["data"]:
            f = item.get("file") or {}
            if (item.get("accordian_name") or {}).get("Name") != "Monthly" or not f.get("url"):
                continue
            period = parse_period(f["name"]) or parse_period(item["title"])
            scheme = (item.get("scheme") or {}).get("Name", "")
            if period:
                name = f"{(item.get('scheme') or {}).get('slug', 'scheme')}_{period}{f.get('ext') or '.xls'}"
                yield Disclosure(amc=SLUG, period=period, url=CMS + f["url"], scheme=scheme, filename=name)
