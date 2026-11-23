import json
import re

from ..base import Disclosure, parse_period

AMC = "Groww Mutual Fund"
SLUG = "groww"
PAGE = "https://www.growwmf.in/statutory-disclosure/portfolio"


def _files(node):
    for f in node.get("files", []):
        yield f
    for sub in node.get("folders", []):
        yield from _files(sub)


def list_disclosures(session):
    html = session.get(PAGE, timeout=60).text
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    root = data["props"]["pageProps"]["filesData"]
    seen = {}
    for folder in root["folders"]:
        if folder["name"].strip().lower() != "portfolio":
            continue
        for f in _files(folder):
            if not re.match(r"mon\w*\s+portfolio", f["name"], re.I):
                continue
            period = parse_period(f["name"])
            if period:
                seen[period] = f
    for period, f in seen.items():
        ext = f["name"].rsplit(".", 1)[-1].lower()
        yield Disclosure(amc=SLUG, period=period, url=f["publicUrl"], filename=f"monthly_portfolio_{period}.{ext}")


def parse(path, amc="", period=""):
    from collections import defaultdict

    from ..parse import parse_file

    rows = parse_file(path, amc=amc, period=period)
    groups = defaultdict(list)
    for h in rows:
        if "deriv" not in h.section.lower():
            groups[(h.source, h.sheet)].append(h)
    # Percent cells are fractions of 1 except in the derivatives block, which defeats the generic rescale
    for hs in groups.values():
        pcts = [h.pct_nav for h in hs if h.pct_nav is not None]
        if pcts and abs(sum(pcts)) <= 1.5:
            for h in hs:
                if h.pct_nav is not None:
                    h.pct_nav = round(h.pct_nav * 100, 6)
    return rows
