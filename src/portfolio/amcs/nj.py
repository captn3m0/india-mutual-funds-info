
from ..base import Disclosure, parse_period
from ..parse import find_header, map_columns, parse_sheet, workbooks

AMC = "NJ Mutual Fund"
SLUG = "nj"
API = "https://www.njmutualfund.com/njmutualfundws/api/njmf-download?nme=127"


def list_disclosures(session):
    data = session.get(API, timeout=60).json()
    seen = set()
    for sec in data.get("sections", []):
        for f in sec.get("files", []):
            url = f.get("url")
            period = parse_period(f.get("label", "")) or parse_period(url or "")
            if not url or not period or url in seen:
                continue
            seen.add(url)
            yield Disclosure(amc=SLUG, period=period, url=url)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            out.extend(parse_sheet(fix(rows), sheet, amc=amc, period=period, source=source))
    return out


def fix(rows):
    # NJ stores % to net assets as fractions; GRAND_TOTAL is missed by the generic end-row regex
    rows = [[str(c).replace("_", " ") if str(c).startswith("GRAND_") else c for c in r] for r in rows]
    hi = find_header(rows)
    if hi is None:
        return rows
    j = map_columns(rows, hi)[0].get("pct_nav")
    if j is not None:
        for r in rows[hi + 1:]:
            if j < len(r) and isinstance(r[j], float):
                r[j] = r[j] * 100
    return rows
