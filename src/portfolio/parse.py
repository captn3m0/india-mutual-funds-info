import datetime
import io
import re
import zipfile
from dataclasses import asdict, dataclass

from python_calamine import CalamineWorkbook

from .base import parse_date

FIELDS = [
    "amc", "period", "as_on", "scheme", "sheet", "section", "subsection", "name",
    "isin", "industry_rating", "quantity", "market_value_lakh", "pct_nav", "ytm", "source",
]

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
SHEET_EXT = (".xls", ".xlsx", ".xlsb", ".xlsm", ".ods")

COLUMNS = {
    "isin": r"^isin",
    "name": r"name of|instrument|issuer|security|company|particulars|scrip",
    "industry_rating": r"industry|rating|sector",
    "quantity": r"quantity|qty|no\.? of|units|shares",
    "market_value": r"market|fair value|value|amount",
    "pct_nav": r"%|percent",
    "ytm": r"yield|ytm|ytc",
}
TOTAL_RE = re.compile(r"^(sub[\s_-]*totals?|totals?|grand[\s_]total|net assets?|net asset value)\b", re.I)
END_RE = re.compile(r"^(grand[\s_]total|net assets?|total net assets?|total aum)\b", re.I)
SUBSECTION_RE = re.compile(r"^\(?([a-z]|[ivx]{1,4}|\d{1,2})[).]\s", re.I)
SCHEME_HINT = re.compile(r"fund|scheme|etf|plan|index|fof|yojana|bees", re.I)


@dataclass
class Holding:
    amc: str = ""
    period: str = ""
    as_on: str = ""
    scheme: str = ""
    sheet: str = ""
    section: str = ""
    subsection: str = ""
    name: str = ""
    isin: str = ""
    industry_rating: str = ""
    quantity: float | None = None
    market_value_lakh: float | None = None
    pct_nav: float | None = None
    ytm: float | None = None
    source: str = ""

    def row(self):
        d = asdict(self)
        return [d[f] if d[f] is not None else "" for f in FIELDS]


def text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return " ".join(str(v).split())


def num(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return None
    s = v.strip().replace(",", "").replace("%", "").replace("₹", "").replace("$", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").strip()
    try:
        f = float(s)
    except ValueError:
        return None
    return -f if neg else f


def workbooks(path: str):
    """Yield (member_name, CalamineWorkbook) for a sheet file or a zip of them."""
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:2] == b"PK" and not _is_ooxml(blob):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for n in z.namelist():
                if n.lower().endswith(SHEET_EXT) and not n.split("/")[-1].startswith("~"):
                    try:
                        wb = CalamineWorkbook.from_filelike(io.BytesIO(z.read(n)))
                    except Exception:
                        continue
                    yield n, wb
    else:
        yield "", CalamineWorkbook.from_filelike(io.BytesIO(blob))


def _is_ooxml(blob: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return "[Content_Types].xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def find_header(rows, limit=60):
    for i, row in enumerate(rows[:limit]):
        cells = [text(c).lower() for c in row]
        if any(re.match(COLUMNS["isin"], c) for c in cells):
            return i
    return None


def map_columns(rows, hi):
    """Map logical column -> index, merging a second header row if present."""
    head = [text(c).lower() for c in rows[hi]]
    if hi + 1 < len(rows):
        nxt = rows[hi + 1]
        if not any(isinstance(c, (int, float)) and not isinstance(c, bool) for c in nxt):
            extra = [text(c).lower() for c in nxt]
            if sum(1 for c in extra if c) >= 2 and not any(ISIN_RE.match(text(c)) for c in nxt):
                head = [f"{a} {b}".strip() for a, b in zip(head, extra + [""] * len(head))]
    cols = {}
    for key, rx in COLUMNS.items():
        for j, c in enumerate(head):
            if c and j not in cols.values() and re.search(rx, c):
                cols[key] = j
                break
    scale = 1.0
    if "market_value" in cols:
        h = head[cols["market_value"]]
        if re.search(r"crore|\bcr\b|cr\.", h):
            scale = 100.0
        elif re.search(r"lakh|lac", h):
            scale = 1.0
        elif re.search(r"thousand|000", h):
            scale = 0.01
    return cols, scale


def find_meta(rows, hi, sheet_name):
    """Scheme name and as-on date from the rows above the header."""
    scheme, as_on, candidates = "", None, []
    for row in rows[:hi]:
        cells = [c for c in row if c not in ("", None)]
        for k, c in enumerate(cells):
            if isinstance(c, (datetime.date, datetime.datetime)) and as_on is None:
                as_on = c.date() if isinstance(c, datetime.datetime) else c
                continue
            t = text(c)
            if as_on is None and re.search(r"as on|as at|ended|for the month|portfolio", t, re.I):
                as_on = parse_date(t)
            m = re.match(r"(?:scheme name|name of the scheme|scheme)\s*[:\-]\s*(.*)", t, re.I)
            if m and not scheme:
                scheme = m.group(1).strip() or (text(cells[k + 1]) if k + 1 < len(cells) else "")
            elif SCHEME_HINT.search(t) and not re.search(r"mutual fund$|^portfolio|back to|pursuant to|regulation", t, re.I):
                candidates.append(t)
    if not scheme and candidates:
        scheme = candidates[0]
    scheme = re.sub(r"^(monthly )?portfolio (statement )?(of|for)\s+", "", scheme, flags=re.I)
    scheme = re.sub(r"\s*[-(,]?\s*(as o[nf]|as at|for (the month of )?[a-z]+,? 20\d\d)\b.*$", "", scheme, flags=re.I)
    return scheme.strip() or sheet_name, as_on


def parse_sheet(rows, sheet_name, **common):
    hi = find_header(rows)
    if hi is None:
        return []
    cols, scale = map_columns(rows, hi)
    if "name" not in cols:
        cols["name"] = max(cols["isin"] - 1, 0)
    scheme, as_on = find_meta(rows, hi, sheet_name)
    out, section, subsection = [], "", ""

    def cell(row, key):
        j = cols.get(key)
        return row[j] if j is not None and j < len(row) else None

    for row in rows[hi + 1:]:
        name = text(cell(row, "name"))
        if not name and not ISIN_RE.match(text(cell(row, "isin")).upper()):
            # Section and cash labels often sit in the ISIN column instead
            name = text(cell(row, "isin"))
        if not name:
            continue
        value, pct = num(cell(row, "market_value")), num(cell(row, "pct_nav"))
        if END_RE.match(name) and (value is not None or pct is not None):
            break
        if TOTAL_RE.match(name):
            continue
        if value is None and pct is None:
            if len(name) < 120:
                if SUBSECTION_RE.match(name):
                    subsection = name
                else:
                    section, subsection = name, ""
            continue
        isin = text(cell(row, "isin")).upper()
        out.append(Holding(
            as_on=str(as_on or ""), scheme=scheme, sheet=sheet_name, section=section,
            subsection=subsection, name=name, isin=isin if ISIN_RE.match(isin) else "",
            industry_rating=text(cell(row, "industry_rating")),
            quantity=num(cell(row, "quantity")),
            market_value_lakh=None if value is None else round(value * scale, 4),
            pct_nav=pct, ytm=num(cell(row, "ytm")), **common,
        ))
    # Percent-formatted cells come through as fractions of 1
    pcts = [h.pct_nav for h in out if h.pct_nav is not None]
    total, peak = sum(pcts), max((abs(p) for p in pcts), default=0)
    if pcts and abs(total) <= 1.5 and (peak <= 1 or abs(total - 1) < 0.02):
        for h in out:
            if h.pct_nav is not None:
                h.pct_nav = round(h.pct_nav * 100, 6)
    return out


def parse_file(path: str, amc: str = "", period: str = "") -> list[Holding]:
    out = []
    for member, wb in workbooks(path):
        source = path.rsplit("/", 1)[-1] + (f"!{member}" if member else "")
        for sheet in wb.sheet_names:
            rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
            out.extend(parse_sheet(rows, sheet, amc=amc, period=period, source=source))
    return out
