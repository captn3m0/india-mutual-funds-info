import json
import re

from ..base import Disclosure, is_sheet, parse_date, parse_period

AMC = "Bank of India Mutual Fund"
SLUG = "boi"
API = "https://www.boimf.in/AjaxService.asmx/GetDocuments"


def list_disclosures(session):
    body = {"pagno": 1, "category": None, "fromDate": None, "toDate": None,
            "LibraryName": "InvestorCorner", "folderName": "MONTHLY PORTFOLIO", "CategoryValue": "no"}
    r = session.post(API, json=body, timeout=120)
    r.raise_for_status()
    seen = set()
    # the endpoint ignores pagno and returns every document in one response
    for doc in json.loads(r.json()["d"]).get("Documents") or []:
        url = doc["FolderUrl"]
        bare = url.split("?")[0]
        label = doc["DocName"] + " " + bare.rsplit("/", 1)[-1]
        d = parse_date(label)
        period = parse_period(doc["DocName"]) or parse_period(bare.rsplit("/", 1)[-1])
        if (d and d.day < 28) or "fortnight" in label.lower():
            continue
        key = (period, re.sub(r"[^a-z0-9]", "", bare.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()))
        if period and is_sheet(bare) and key not in seen:
            seen.add(key)
            yield Disclosure(amc=SLUG, period=period, url=url)


FUT_RE = re.compile(r"\bfut\b|\bfutures?\b|^deriv", re.I)
TOTAL_NAME = re.compile(r"\btotals?\)?\s*$", re.I)


def parse(path, amc="", period=""):
    from ..parse import TOTAL_RE, parse_sheet, workbooks

    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            rows = [[("Total " + c if isinstance(c, str) and TOTAL_NAME.search(c.strip()) and not TOTAL_RE.match(c.strip()) else c) for c in r] for r in rows]
            hs = parse_sheet(rows, sheet, amc=amc, period=period, source=source)
            futs = [h for h in hs if FUT_RE.search(f"{h.section} {h.name}") or (re.search(r"hedged", h.section, re.I) and not h.isin and (h.pct_nav or 0) < 0)]
            total, fsum = sum(h.pct_nav or 0 for h in hs), sum(h.pct_nav or 0 for h in futs)
            peak = max((abs(h.pct_nav or 0) for h in hs), default=0)
            for k, drop in ((1, False), (1, True), (100, False), (100, True)):
                if (k == 1 or peak <= 1) and (drop <= bool(futs)) and 95 <= (total - fsum * drop) * k <= 105:
                    for h in hs:
                        h.pct_nav = None if drop and h in futs else (h.pct_nav * k if h.pct_nav is not None else None)
                    break
            out.extend(hs)
    return out
