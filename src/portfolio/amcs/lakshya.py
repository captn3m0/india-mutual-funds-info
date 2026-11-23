import datetime
import time

from ..base import Disclosure

AMC = "Lakshya Mutual Fund"
SLUG = "lakshya"
API = "https://lakshyafunds.com/api/ext"


def list_disclosures(session):
    schemes = session.get(f"{API}/schemes", timeout=60).json()
    today = datetime.date.today()
    for sc in schemes:
        # First scheme allotment was September 2026
        for y in range(2026, today.year + 1):
            for m in range(1, 13):
                if y == 2026 and m < 9 or (y, m) > (today.year, today.month):
                    continue
                url = f"{API}/disclosures/portfolio-disclosure/download?scheme_id={sc['scheme_id']}&reporting_month={m}&reporting_year={y}"
                r = session.get(url, timeout=60)
                time.sleep(0.3)
                if r.status_code == 200 and "spreadsheet" in r.headers.get("content-type", ""):
                    name = f"{sc['scheme_name'].replace(' ', '_')}_{y}-{m:02d}.xlsx"
                    yield Disclosure(amc=SLUG, period=f"{y}-{m:02d}", url=url, filename=name, scheme=sc["scheme_name"])
