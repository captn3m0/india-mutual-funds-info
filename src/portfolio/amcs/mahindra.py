import json

from ..base import Disclosure, aes_cbc, is_sheet, parse_period

AMC = "Mahindra Manulife Mutual Fund"
SLUG = "mahindra"
API = "https://investorapi.mahindramanulife.com/api/v1/web/preLogin/downloads"
PATH = ("MANDATORY DISCLOSURES", "Portfolio Disclosure", "Monthly Portfolio Disclosure")
# The API wraps some responses as {"payload": <AES>}; constants are from the site's JS bundle
KEY, IV = b"mahindra2024mahindra2024mahindra", b"hasnainsheikh202"


def _walk(cats, path=()):
    for c in cats:
        here = path + (c["categoryName"].strip(),)
        for f in c.get("files") or []:
            yield here, f
        yield from _walk(c.get("subcategories") or [], here)


def list_disclosures(session):
    r = session.get(API, headers={"Accept": "application/json", "platform": "web"}, timeout=180)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "payload" in data:
        data = data["payload"]
    if isinstance(data, str):
        data = json.loads(aes_cbc(KEY, IV, data))
    seen = set()
    for path, f in _walk(data["data"]):
        url = f.get("fileUrl") or ""
        if path[:3] != PATH or not is_sheet(url) or url in seen:
            continue
        period = parse_period(f["title"])
        if period:
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url)


def _label(row):
    return " ".join(str(row[1]).split()) if len(row) > 1 else ""


def parse(path, amc="", period=""):
    from ..parse import parse_sheet, workbooks

    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            if "transaction" in sheet.lower():
                continue
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            # A repeated "Net Receivables / (Payables)" row is the subtotal of the rows above it
            keep = [r for i, r in enumerate(rows) if not (
                i and "receivables" in _label(r).lower() and _label(r) == _label(rows[i - 1])
            )]
            out.extend(parse_sheet(keep, sheet, amc=amc, period=period, source=source))
    return out
