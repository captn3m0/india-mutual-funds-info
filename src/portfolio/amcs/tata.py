from urllib.parse import unquote

import re

from ..base import MONTHS, Disclosure, is_sheet
from ..parse import find_header, parse_sheet, text, unhedge, workbooks

AMC = "Tata Mutual Fund"
SLUG = "tata"
MON = re.compile(r"(%s)[\s_\-.]*((?:19|20)\d\d)" % "|".join(sorted(MONTHS, key=len, reverse=True)))
INDEX = "https://www.tatamutualfund.com/schemes-related/portfolio"


def list_disclosures(session):
    html = session.get(INDEX, timeout=60).text
    best = {}
    for url in sorted(set(re.findall(r'https://www\.tatamutualfund\.com/system/files/[^"\\\s<>]+', html))):
        name = unquote(url.split("?")[0].rsplit("/", 1)[-1]).lower()
        if not is_sheet(url) or "monthly" not in name or "portfolio" not in name:
            continue
        m = MON.search(name)
        if not m:
            continue
        period = f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"
        # Half-yearly-format files only fill months with no regular monthly file
        rank = "half" in name
        if period not in best or rank < best[period][0]:
            best[period] = (rank, url)
    for period, (_, url) in best.items():
        yield Disclosure(amc=SLUG, period=period, url=url, filename=unquote(url.rsplit("/", 1)[-1]))


ASON = re.compile(r"as on\s+(\d\d)[/.-](\d\d)[/.-](\d{4}|\d\d)", re.I)
STOP = re.compile(r"^(net assets|details of|disclosure of|name of the schemes?)\b", re.I)


FMP = re.compile(r"(SERIES)\s*\d+\s*(SCHEME)\s*-\s*[A-Z]\b", re.I)


def fix_fmp(scheme, sheet):
    m = re.fullmatch(r"TFM(\d+)([A-Z])", sheet)
    return FMP.sub(rf"\1 {m.group(1)} \2 - {m.group(2)}", scheme, count=1) if m and FMP.search(scheme) else scheme


def drop_subtotals(hs):
    keep = []
    for h in hs:
        acc, hit = 0.0, False
        for k, p in enumerate(reversed(keep), 1):
            if p.sheet != h.sheet or p.isin or p.pct_nav is None:
                break
            acc += p.pct_nav
            hit = hit or ((k >= 2 or re.search(r"deposits?$", h.name, re.I)) and not h.isin and h.pct_nav and abs(acc - h.pct_nav) <= 0.005 * abs(acc))
        if not hit:
            keep.append(h)
    return keep


def parse(path, amc="", period=""):
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = [list(r) for r in wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)]
            hi = find_header(rows)
            if hi is None:
                continue
            scheme, as_on = "", ""
            for r in rows[:hi]:
                for c in r:
                    t = text(c)
                    m = ASON.search(t)
                    if m and not as_on:
                        y = m.group(3)
                        as_on = f"{2000 + int(y) if len(y) == 2 else y}-{m.group(2)}-{m.group(1)}"
                    if not scheme and t and t.lower() != "index" and rows.index(r) < 3:
                        scheme = t
            for j in range(hi, min(hi + 4, len(rows))):
                if any(re.match(r"yield", text(c), re.I) for c in rows[j]):
                    rows[j] = [re.sub(r"mkt val", "market value", re.sub(r"yield.*", "ytm", text(c), flags=re.I), flags=re.I) for c in rows[j]]
            end = next((i for i, r in enumerate(rows[hi + 1:], hi + 1) if STOP.match(text(r[0]) if r else "")), len(rows))
            for h in parse_sheet(rows[:end], sheet, amc=amc, period=period, source=source):
                if not h.isin and (re.search(r"\btotal\b", h.name, re.I) or h.name == "EQUITY RELATED" or h.name.upper() == h.section.upper()):
                    continue
                h.scheme, h.as_on = fix_fmp(scheme or h.scheme, sheet), as_on or h.as_on
                out.append(h)
    sheets = {}
    for h in drop_subtotals(out):
        sheets.setdefault((h.source, h.sheet), []).append(h)
    return [h for hs in sheets.values() for h in unhedge(hs)]
