"""Parse AMFI Scheme Summary Documents (details/*.xml) into CSV files."""
import csv
import datetime
import glob
import json
import os
import re
import sys

import lxml.etree

from portfolio.base import parse_date

NA = re.compile(r"^(n\.?\s*/?\s*a\.?|nil|none|null|not\s+a(pp?licable|vailable)|-+|0)[.,]?$", re.I)
ISIN = re.compile(r"\bIN[A-Z0-9]{9}\d\b")
AMFI_CODE = re.compile(r"1[0-5]\d{4}")
SEBI_CODE = re.compile(r"\b[A-Z0-9&]{2,5}/[OCI]/[A-Z]/[A-Z0-9]{2,4}/\d\d/\d\d/\d{4}\b")
CELLS = {"cell", "table-cell"}
# canonical field -> pattern over the label with everything but letters and digits removed
LABELS = {
    "name": r"^(fund|scheme)name$",
    "sebi_code": r"^sebi(scheme)?codes?",
    "isins": r"^isins?",
    "amfi_codes": r"^amficodes?",
    "rta_code": r"^rtacode",
    "category": r"^categoryasper",
    "fund_type": r"^fundtype",
    "riskometer_at_launch": r"^riskometer.*launch",
    "riskometer": r"^riskometeras",
    "potential_risk_class": r"^potentialriskclass",
    "benchmark_tier_1": r"^benchmar(k|ch)tier1",
    "benchmark_tier_2": r"^benchmar(k|ch)tier2",
    "nfo_open_date": r"^nfoopen",
    "nfo_close_date": r"^nfoclose",
    "allotment_date": r"^allotmentdate",
    "reopen_date": r"^reopen",
    "maturity_date": r"^maturitydate",
    "face_value": r"^facevalue",
    "fund_managers": r"^fundmanager\d*name",
    "expense_ratio": r"^a(nnual|ctual)expenses?",
    "exit_load": r"^exitload",
    "custodian": r"^custodian",
    "auditor": r"^auditor",
    "registrar": r"^registrar",
    "listing": r"^listingdetails",
}
LABELS = {k: re.compile(v) for k, v in LABELS.items()}
MULTI = ("isins", "amfi_codes", "fund_managers")
DATES = ["nfo_open_date", "nfo_close_date", "allotment_date", "reopen_date", "maturity_date"]
SCHEME_FIELDS = ["mf_id", "amc_id"] + [k for k in LABELS if k not in ("isins", "amfi_codes")]


def local(el):
    return lxml.etree.QName(el).localname if isinstance(el.tag, str) else ""


def flat(el):
    return " ".join("".join(el.itertext()).split())


def pairs(el):
    """(label, value) pairs from any of the layouts AMCs upload: tagged records or label/value rows."""
    kids = [c for c in el if isinstance(c.tag, str)]
    if local(el) == "Class" and el.get("name"):
        yield el.get("name"), flat(el)
    elif len(kids) >= 15 and sum(len(c) == 0 for c in kids) > len(kids) * 0.8:
        for c in kids:
            if len(c):
                yield from pairs(c)
            else:
                yield local(c), flat(c)
    elif 1 <= len(kids) < 15 and all(len(c) == 0 or local(c).lower() in CELLS for c in kids):
        # per-plan blocks carry their identifiers in tags of their own
        tagged = [(local(c), flat(c)) for c in kids if field_for(local(c)) in ("isins", "amfi_codes")]
        yield from tagged or row([flat(c) for c in kids])
    else:
        for c in kids:
            yield from pairs(c)


def field_for(label):
    key = re.sub(r"[^a-z0-9]", "", label.lower())
    return next((f for f, rx in LABELS.items() if rx.search(key)), None)


def iso_date(value):
    """ISO date from free text, or from the Excel serial some AMCs leave in place of a date."""
    if re.fullmatch(r"[2-5]\d{4}(\.0)?", value):
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(value)))).isoformat()
    d = parse_date(value)
    return d.isoformat() if d else ""


def amfi_codes(value):
    """Six digit AMFI codes, including runs of them written without separators."""
    runs = [r for r in re.findall(r"\d+", value) if len(r) % 6 == 0]
    chunks = {r[i:i + 6] for r in runs for i in range(0, len(r), 6)}
    return sorted(c for c in chunks if AMFI_CODE.fullmatch(c))


def row(cells):
    cells = [c for c in cells if c]
    if cells and re.fullmatch(r"\d+(\.0)?", cells[0]):
        cells = cells[1:]
    if len(cells) >= 2:
        yield cells[0], "\n".join(cells[1:])


def json_pairs(node):
    if isinstance(node, dict):
        values = list(node.values())
        if all(not isinstance(v, (dict, list)) for v in values):
            yield from row(["" if v is None else str(v).strip() for v in values])
        for v in values:
            yield from json_pairs(v)
    elif isinstance(node, list):
        for v in node:
            yield from json_pairs(v)


def read(path):
    """Canonical field -> text for one document; unknown labels are dropped."""
    raw = open(path, "rb").read()
    if raw.lstrip(b"\xef\xbb\xbf \r\n\t")[:1] in (b"{", b"["):
        found = json_pairs(json.loads(raw.decode("utf-8-sig")))
    else:
        parser = lxml.etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=True)
        root = lxml.etree.fromstring(raw, parser)
        found = pairs(root) if root is not None else []
    out = {}
    for label, value in found:
        # values are often double-escaped by the uploader
        value = value.replace("&amp;", "&").strip()
        field = field_for(label)
        if not field or not value or (NA.match(value) and field not in MULTI):
            continue
        out[field] = f"{out[field]}; {value}" if field in out and field in MULTI else out.get(field, value)
    # ISINs are unambiguous, and some AMCs put them under the wrong label
    out["isins"] = " ".join(sorted(set(ISIN.findall(raw.decode("utf-8", "replace").upper()))))
    return {k: v for k, v in out.items() if v}


def main(src="details", dest="."):
    with open("amfi_funds.csv", newline="") as f:
        amfi = {r["MF_ID"]: r for r in csv.DictReader(f)}
    schemes, isins, codes, empty = [], [], [], []
    for path in sorted(glob.glob(f"{src}/*.xml"), key=lambda p: int(os.path.basename(p)[:-4])):
        mf_id = os.path.basename(path)[:-4]
        doc = read(path)
        if not doc:
            empty.append(mf_id)
            continue
        known = amfi.get(mf_id, {})
        doc["name"] = " ".join(doc.get("name", known.get("MF_NAME", "")).split())
        for field in DATES:
            doc[field] = iso_date(doc.get(field, ""))
        m = SEBI_CODE.search(doc.get("sebi_code", "").upper().replace(" ", ""))
        doc["sebi_code"] = m.group(0) if m else ""
        doc = {k: " ".join(v.split()) for k, v in doc.items()}
        schemes.append({**doc, "mf_id": mf_id, "amc_id": known.get("AMC_ID", "")})
        isins += [(mf_id, i) for i in sorted(set(ISIN.findall(doc.get("isins", "").upper())))]
        codes += [(mf_id, c) for c in amfi_codes(doc.get("amfi_codes", ""))]
    with open(f"{dest}/schemes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCHEME_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(schemes)
    for name, header, rows in (("scheme_isins", "isin", isins), ("scheme_amfi_codes", "amfi_code", codes)):
        with open(f"{dest}/{name}.csv", "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["mf_id", header])
            w.writerows(rows)
    print(f"{len(schemes)} schemes, {len(isins)} ISINs, {len(codes)} AMFI codes; unparsed: {' '.join(empty) or 'none'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
