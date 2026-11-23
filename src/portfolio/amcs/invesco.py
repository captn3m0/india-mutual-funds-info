import re
import time

from ..base import Disclosure
from ..parse import find_header, parse_sheet, text, workbooks

AMC = "Invesco Mutual Fund"
SLUG = "invesco"
API = "https://www.invescomutualfund.com/api"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def list_disclosures(session):
    session.headers["Accept"] = "application/json"
    classes = session.get(f"{API}/ClassificationCompleteMonthlyHoldings", timeout=60).json()
    classes = [c["FunClassificationValue"] for c in classes if c["FunClassificationValue"] != "Select"]
    years = [r["Year"] for r in session.get(f"{API}/CompleteMonthlyHoldings?year=0", timeout=60).json()]
    seen = set()
    for year in years:
        for cls in classes:
            r = session.get(f"{API}/CompleteMonthlyHoldings", params={"year": year, "classification": cls}, timeout=60)
            time.sleep(0.2)
            if r.status_code != 200:
                continue
            for row in r.json():
                for i, mon in enumerate(MONTHS, 1):
                    url = row.get(f"{mon}Url")
                    if not url or url in seen or "sample-file" in url:
                        continue
                    seen.add(url)
                    ext = re.search(r"\.(xlsx?|zip)(?:\?|$)", url, re.I)
                    slug = re.sub(r"[^A-Za-z0-9]+", "_", row["Name"]).strip("_")
                    stem = re.sub(r"[^A-Za-z0-9]+", "_", url.split("?")[0].rsplit("/", 1)[-1].rsplit(".", 1)[0])[-40:]
                    name = f"{slug}_{stem}_{year}-{i:02d}.{ext[1].lower() if ext else 'xlsx'}"
                    yield Disclosure(amc=SLUG, period=f"{year}-{i:02d}", url=url, scheme=row["Name"], filename=name)


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = [list(r) for r in wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)]
            if find_header(rows) is None:
                # Gold/silver ETF sheets have an unlabelled code column instead of ISIN
                for r in rows[:30]:
                    if len(r) > 1 and not text(r[0]) and re.match(r"name of the instrument", text(r[1]), re.I):
                        r[0] = "ISIN"
                        break
            out += parse_sheet(rows, sheet, amc=amc, period=period, source=source)
    return out
