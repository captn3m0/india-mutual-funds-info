import re
import time

from ..base import Disclosure
from ..parse import parse_sheet, workbooks

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
