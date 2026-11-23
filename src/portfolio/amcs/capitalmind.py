import re

from ..base import Disclosure, links, month_end, parse_date, parse_period
from ..parse import parse_sheet, workbooks

AMC = "Capitalmind Mutual Fund"
SLUG = "capitalmind"
IMPERSONATE = "chrome"
INDEX = "https://www.capitalmindmf.com/statutory-disclosures.html"
SKIP = re.compile(r"fortnight|half|dashboard|performance|^IR_", re.I)
SCHEMES = {"CMFLEXI": "Flexi Cap", "CMLIQ": "Liquid", "CMMAAF": "Multi Asset Allocation", "CMARB": "Arbitrage"}


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    seen = set()
    for url, _ in links(html, INDEX):
        name = url.split("?")[0].rsplit("/", 1)[-1]
        if "/uploads/" not in url or not name.lower().endswith((".xlsx", ".xls")):
            continue
        if SKIP.search(name) or "portfolio" not in name.lower() or url in seen:
            continue
        seen.add(url)
        clean = re.sub(r"_[0-9a-f]{10}(_[0-9a-f]{10})?(?=\.)", "", name)
        period = parse_period(clean)
        day = parse_date(clean)
        if not period or (day and day != month_end(period)):
            continue
        code = name.split("_", 1)[0]
        if code == "CMLIQ" and period < "2025-11":
            period = f"{int(period[:4]) + 1}{period[4:]}"
        scheme = SCHEMES.get(code, "Liquid" if "Liquid" in name else "Flexi Cap" if code == "Capitalmind" else "")
        yield Disclosure(amc=SLUG, period=period, url=url, scheme=scheme)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            for r in rows[:15]:
                cells = [c for c in r if c not in ("", None)]
                if len(cells) == 2 and re.search(r"as on", str(cells[0]), re.I):
                    r[:] = [f"{cells[0]} {cells[1]}"] + [""] * (len(r) - 1)
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
