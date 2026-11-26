import re
import time

from ..base import MONTHS, Disclosure
from ..parse import find_header, parse_sheet, text, workbooks

AMC = "Axis Mutual Fund"
SLUG = "axis"
IMPERSONATE = "chrome"
API = "https://www.axismf.com/cms/"
BODY = {"sdType": "yearMonthSchemeDocs", "sdID": "sdMonthSchemePortfolio"}
SHEET = (".xls", ".xlsx", ".xlsb", ".zip")


def call(session, path, headers, **extra):
    for attempt in range(4):
        time.sleep(0.3 + attempt * 3)
        r = session.post(API + path, json={**BODY, **extra}, headers=headers, timeout=60)
        if r.status_code < 500:
            break
    r.raise_for_status()
    return r.json().get("data") or {}


def is_monthly(doc):
    name = doc["documentName"].strip()
    if not doc["docuementURL"].lower().endswith(SHEET):
        return False
    return bool(re.search(r"monthly", name, re.I) or re.fullmatch(r"(\d\d-)?[A-Za-z]{3,9}", name) and name.split("-")[-1].lower() in MONTHS)


def disclosure(doc, period):
    name = doc["docuementURL"].split("?")[0].rsplit("/", 1)[-1]
    return Disclosure(amc=SLUG, period=period, url=doc["docuementURL"], filename=f"{period}_{name}")


def list_disclosures(session):
    token = session.post(API + "token", json={}, timeout=60).json()["data"]["token"]
    headers = {"Authorization": token}
    meta = call(session, "get-scheme-documents", headers)
    codes = list(dict.fromkeys(s["schemeCode"] for s in meta["schemeCategories"]))
    seen = set()
    for year in sorted(meta["years"]):
        for month in meta["months"]:
            period = f"{year}-{MONTHS[month.lower()]:02d}"
            docs = call(session, "get-scheme-documents", headers, year=year, month=month, schemeCode="Consolidated").get("documentList", [])
            hits = [d for d in docs if is_monthly(d)]
            sheets = [d for d in docs if d["docuementURL"].lower().endswith(SHEET)]
            if not hits and len(sheets) == len(docs) == 1:
                hits = sheets
            # Months without a consolidated workbook only have per-scheme files
            if not hits and docs:
                for code in codes[1:]:
                    hits += [d for d in call(session, "get-scheme-documents", headers, year=year, month=month, schemeCode=code).get("documentList", []) if is_monthly(d)]
            for d in hits:
                if d["docuementURL"] not in seen:
                    seen.add(d["docuementURL"])
                    yield disclosure(d, period)


def parse(path, amc="", period=""):
    """Generic parsing, except Aug 2017 labels % to NAV as a second market value column."""
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = [list(r) for r in wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)]
            hi = find_header(rows)
            if hi is not None:
                head = [text(c).lower() for c in rows[hi]]
                market = [j for j, c in enumerate(head) if c.startswith("market")]
                if len(market) == 2 and not any("%" in c or "net assets" in c for c in head):
                    rows[hi][market[1]] = "% to Net Assets"
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
