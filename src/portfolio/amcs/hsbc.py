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


def parse(path, amc="", period=""):
    from ..parse import find_header, parse_sheet, text, workbooks

    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            if re.match(r"(notes?|disclaimer)\b", sheet.strip(), re.I) or (rows and re.match(r"notes?\b", text(rows[0][0]) if rows[0] else "", re.I)):
                continue
            hi = find_header(rows)
            if hi is not None and not text(rows[hi][0]) and text(rows[hi][1]).lower().startswith("isin"):
                rows[hi][0] = "Name of the Instrument"
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    sheets = {}
    for h in out:
        sheets.setdefault(h.scheme, {})[(h.source, h.sheet)] = h.as_on[:7]
    stale = {(k, v) for k, d in sheets.items() if len(d) > 1 and period in d.values() for v, m in d.items() if m != period}
    return [h for h in out if (h.scheme, (h.source, h.sheet)) not in stale]
