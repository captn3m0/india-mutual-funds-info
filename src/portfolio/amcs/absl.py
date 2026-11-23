import re

from ..base import Disclosure, parse_date, parse_period
from ..parse import Holding, find_header, num, parse_sheet, text, workbooks

AMC = "Aditya Birla Sun Life Mutual Fund"
SLUG = "absl"
BASE = "https://mutualfund.adityabirlacapital.com"
API = BASE + "/postlogin/CustomApi/Resources/FactsheetAccordionById"
ACCORDION = "3ccab227-9de5-4494-b78d-2b4f7c0c054a"
CTYPE = "/sitecore/content/Root/BSL/Library/Lists/FAQ/Customer Types/Individual"


def list_disclosures(session):
    r = session.get(
        API,
        params={"id": ACCORDION, "ctype": CTYPE, "month": " ", "year": 0},
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=120,
    )
    r.raise_for_status()
    seen = set()
    for item in r.json()["AccordionList"]:
        title, url = item["ResourceLink"], item["pdfUrl"]
        # Skip the off-cycle open-ended debt and FoF updates
        if not title.startswith("Monthly Portfolio") or url in seen:
            continue
        seen.add(url)
        # The azureedge CDN host is retired; the same paths are served from the main site
        url = url.replace("https://abcscprod.azureedge.net", BASE)
        title = re.sub(r"(?i)janaury", "January", title)
        d = parse_date(title)
        period = f"{d.year}-{d.month:02d}" if d else parse_period(title)
        if period:
            yield Disclosure(amc=SLUG, period=period, url=url)


ROMAN = re.compile(r"^\(?([ivx]+)\)?$", re.I)
SECTIONS = re.compile(r"^(?:(bonds)|(securitised)|(money market)|(government sec)|(fixed dep))", re.I)
HEADS = ("name of the issuer", "obligor", "originator", "bank name", "details of securities")


def parse(path, amc="", period=""):
    out, seen = [], set()
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        common = dict(amc=amc, period=period, source=source)
        sheets = {s: wb.get_sheet_by_name(s).to_python(skip_empty_area=False) for s in wb.sheet_names}
        if any(find_header(r) is not None for r in sheets.values()):
            for s, rows in sheets.items():
                out.extend(parse_sheet(rows, s, **common))
        elif "Annexure" in sheets and "Portfolio format" in sheets:
            rows = _legacy(sheets, member, common)
            if rows and rows[0].scheme.casefold() not in seen:
                seen.add(rows[0].scheme.casefold())
                out.extend(rows)
    return out


def _legacy(sheets, member, common):
    summ, ann = sheets["Portfolio format"], sheets["Annexure"]
    top = [text(c) for r in summ[:8] for c in r if text(c)]
    as_on = next((d for d in map(parse_date, top + [text(c) for r in ann[:4] for c in r]) if d), "")
    scheme = next((re.sub(r"^.*?mutual fund\s*-\s*", "", t, flags=re.I).strip() for t in top if re.search(r"mutual fund\s*-\s*\S", t, re.I)), "")
    if not scheme:
        scheme = re.sub(r"^birla sun life mutual fund\s*-\s*", "", member.rsplit("/", 1)[-1].rsplit(".", 1)[0], flags=re.I).strip()
    scheme = re.sub(r"\s+A\d+:[A-Z]\d+$", "", scheme)
    base = dict(as_on=str(as_on), scheme=scheme, **common)

    lines, names, net, mult, grp = {}, {}, None, 100.0, ""
    for r in summ[8:]:
        c = [text(x) for x in r] + ["", ""]
        v = [x for x in r if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if re.match(r"^[A-G]$", c[0]):
            grp = c[0]
            lines.setdefault(grp, [re.sub(r"\s*of\s*:?$", "", c[1]), 0.0, 0.0])
        if len(v) < 2:
            continue
        if re.match(r"^net assets", c[1], re.I):
            net, mult = v[0], 100.0 if v[1] <= 1.5 else 1.0
        elif not re.search(r"total", c[1], re.I):
            m = ROMAN.match(c[0])
            if m:
                names[m.group(1).upper()] = c[1]
            if m or re.match(r"^[D-G]$", c[0]):
                lines[grp][1] += v[0]
                lines[grp][2] += v[1]
    out, got = [], {}

    def add(sheet, section, name, rating, value, pct, key):
        out.append(Holding(sheet=sheet, section=section, name=name, industry_rating=rating,
                           market_value_lakh=None if value is None else round(value, 4),
                           pct_nav=round(pct * mult, 6), **base))
        g = got.setdefault(key, [0.0, 0.0])
        g[0] += value or 0
        g[1] += pct

    cols, sec, cat, catname, pending = {}, "", "", "", None
    for r in ann + [["Bonds"]]:
        c = [text(x) for x in r] + [""] * 8
        used = [x for x in c if x]
        head = SECTIONS.match(used[-1]) if used and not any(isinstance(x, float) for x in r) else None
        if head:
            if pending:
                add("Annexure", *pending)
            pending, sec, cat, catname, cols = None, "ABCDE"[head.lastindex - 1], "", "", {}
            continue
        low = [x.lower() for x in c]
        if any("market value" in x or x.startswith("amount") for x in low):
            cols = {}
            for j, x in enumerate(low):
                if ("market value" in x or x.startswith("amount")) and "mv" not in cols:
                    cols["mv"] = j
                elif x.startswith("rating") and "rt" not in cols:
                    cols["rt"] = j
                elif x.startswith("%") and "pct" not in cols:
                    cols["pct"] = j
                elif any(x.startswith(h) for h in HEADS) and "nm" not in cols:
                    cols["nm"] = j
            continue
        roman = next((j for j, x in enumerate(c[:4]) if ROMAN.match(x)), None)
        mv = num(r[cols["mv"]]) if "mv" in cols and cols["mv"] < len(r) else None
        pct = num(r[cols["pct"]]) if "pct" in cols and cols["pct"] < len(r) else None
        if mv is not None and net and (pct is None or abs(pct - mv / net * 100 / mult) > 0.005 * 100 / mult):
            pct = mv / net * 100 / mult
        if roman is not None:
            nm = c[roman + 1]
            if not mv:
                cat, catname = ROMAN.match(c[roman]).group(1).upper(), nm
                continue
            if out and mv and out[-1].sheet == "Annexure" and abs(mv - (out[-1].market_value_lakh or 0)) < 1e-3 and not pending:
                continue
            if pending and mv and abs(mv - pending[3]) < 1e-6 and nm != pending[1]:
                add("Annexure", pending[0], nm, "", mv, pct or 0, sec)
                pending = None
                continue
            if pending:
                add("Annexure", *pending)
            pending, cat, catname = None, ROMAN.match(c[roman]).group(1).upper(), nm
            if mv and nm:
                pending = (names.get(cat, nm), nm, "", mv, pct or 0, sec)
            continue
        name = c[cols["nm"]] if "nm" in cols else ""
        if not name or mv is None or re.match(r"^(sub[\s-]*)?total", name, re.I):
            continue
        pending = None
        section = (catname or names.get(cat, "")) if sec in "ABC" else lines.get(sec, [sec])[0]
        add("Annexure", section, name, c[cols["rt"]] if "rt" in cols else "", mv, pct or 0, sec)

    gaps = {k: v[2] - got.get(k, [0.0, 0.0])[1] for k, v in lines.items()}
    over = -sum(g for k, g in gaps.items() if g < 0 and k in "ABCDEG")
    for key, (label, mv, pct) in lines.items():
        gap = gaps[key]
        if key in "ABCDEG":
            cut = min(max(gap, 0), over)
            over -= cut
            gap -= cut
            if gap <= 0:
                continue
        if abs(gap) * mult > 0.01:
            add("Portfolio format", label, label, "", gap * (net or 0) * mult / 100, gap, key)
    return out
