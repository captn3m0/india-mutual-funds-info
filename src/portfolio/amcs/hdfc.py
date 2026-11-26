import io
import re
import time
from urllib.parse import quote

from python_calamine import CalamineWorkbook

from ..base import Disclosure
from ..parse import parse_sheet, text, workbooks

AMC = "HDFC Mutual Fund"
SLUG = "hdfc"
IMPERSONATE = "chrome"
API = "https://cms.hdfcfund.com/en/hdfc/api/v2/disclosures/"
HEADERS = {"origin": "https://www.hdfcfund.com", "referer": "https://www.hdfcfund.com/"}


def post(session, endpoint, **data):
    r = session.post(API + endpoint, data={"type": "monthly", **data}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()["data"]


def list_disclosures(session):
    years = post(session, "monthfortportfolio", year=0, month=0)["Years"]["values"]
    for year in sorted(years, reverse=True):
        months = post(session, "portfolioMonths", year=year)["months"] or {}
        for month in months:
            time.sleep(0.3)
            seen = set()
            files = post(session, "monthfortportfolio", year=year, month=month).get("files") or []
            for f in files:
                url = f["file"]["url"]
                name = f["file"]["filename"]
                if name in seen:
                    continue
                seen.add(name)
                period = f"{int(year):04d}-{int(month):02d}"
                yield Disclosure(amc=SLUG, period=period, url=url, filename=name, scheme=name.rsplit(".", 1)[0])


def follow(session, d, body):
    """Sep 2021 to Sep 2022 debt funds were published as a sheet linking to the real file."""
    if len(body) > 20000 or body[:2] != b"PK":
        return body
    wb = CalamineWorkbook.from_filelike(io.BytesIO(body))
    rows = wb.get_sheet_by_name(wb.sheet_names[0]).to_python(skip_empty_area=False)
    url = next((t for r in rows if "Monthly" in map(text, r) for t in map(text, r) if t.startswith("http")), None)
    if not url:
        return body
    r = session.get(quote(url, safe=":/%"), headers=HEADERS, timeout=180)
    if r.status_code != 200 or r.content[:2] != b"PK":
        raise ValueError(f"linked file {url} gave HTTP {r.status_code}")
    return r.content


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            # "Coupon (%)" would otherwise be taken for the % to NAV column
            rows = [["coupon" if re.match(r"coupon", str(c), re.I) else c for c in r] for r in rows[:20]] + rows[20:]
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
