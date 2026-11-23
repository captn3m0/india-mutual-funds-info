import re
from urllib.parse import quote, unquote

from ..base import Disclosure, parse_date
from ..parse import find_header, map_columns, parse_sheet, text, workbooks

AMC = "PGIM India Mutual Fund"
SLUG = "pgim"
API = "https://www.pgimindia.com/api/v1/brochure/published/disclosure"
SECTION = {"headerId": 2, "sectionId": "SECTION_747960037"}


def list_disclosures(session):
    r = session.post(API, json=SECTION, timeout=120)
    r.raise_for_status()
    seen = set()
    for tab in r.json()["data"]:
        for item in tab["content"]:
            url = item["pdfPath"].strip()
            d = parse_date(item["dateMonthYear"])
            if url in seen or not d or not re.search(r"\.(xlsx?|xlsb)$", url, re.I):
                continue
            seen.add(url)
            title = re.sub(r"\s+\w{3,9}\.?\s+\d{4}$", "", item["title"].strip())
            scheme = "" if tab["tabId"] == 66 else title
            yield Disclosure(
                amc=SLUG, period=f"{d.year}-{d.month:02d}", url=quote(unquote(url), safe=":/%"),
                filename=unquote(url.rsplit("/", 1)[-1]), scheme=scheme,
            )


def fix_rows(rows):
    hi = find_header(rows)
    if hi is None:
        return rows
    cols, _ = map_columns(rows, hi)
    j = cols.get("name", max(cols["isin"] - 1, 0))
    label = ""
    for i in range(hi + 1, len(rows)):
        row = rows[i]
        cell = text(row[j]) if j < len(row) else ""
        # Repo-style lines carry the label on the row above and values below it
        if not cell and not text(row[cols["isin"]] if cols["isin"] < len(row) else "") and label and any(
            isinstance(c, (int, float)) and not isinstance(c, bool) for c in row
        ):
            rows[i] = row[:j] + [label] + row[j + 1:]
        elif cell and not any(isinstance(c, (int, float)) and not isinstance(c, bool) for c in row):
            label = cell
    return rows


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = [list(r) for r in wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)]
            out.extend(drop_subtotals(parse_sheet(fix_rows(rows), sheet, amc=amc, period=period, source=source)))
    return out


def drop_subtotals(hs):
    # Old layouts print group subtotals as unnamed-ISIN rows followed by their members
    keep = []
    for i, h in enumerate(hs):
        if not h.isin and h.quantity is None and h.pct_nav:
            total, n = 0.0, 0
            for m in hs[i + 1:]:
                if m.isin or m.quantity is not None:
                    total, n = total + (m.pct_nav or 0), n + 1
                else:
                    break
            if n and abs(total - h.pct_nav) < 0.5:
                continue
        keep.append(h)
    return keep
