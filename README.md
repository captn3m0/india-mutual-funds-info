# Mutual Funds Information

:warning: This repository used to be at `captn3m0/kuvera-mutual-funds-lookup`. Since now it contains more than just the Kuvera Identifiers, I've renamed it to `captn3m0/india-mutual-funds-info`.

A SQLite build and an HTTP API are WIP. Stay tuned. All data will be published in CSV/SQLite/HTTP-API formats, with standard identifiers (ISINs/SEBI-IDs).

## Mutual Funds Information

`amfi_funds.csv` contains AMC_ID,MF_ID,MF_NAME. All identifiers are AMFI Identifiers here.

## Scheme Details

Parsed from the Scheme Summary Documents (SSD) that each AMC uploads to AMFI, kept as
`details/<MF_ID>.xml`. AMCs upload these in many different layouts, so fields are matched
by label and free text is kept as written.

- `schemes.csv` has one row per scheme: `mf_id`, `amc_id`, name, SEBI scheme code, category,
  riskometer, benchmarks, NFO/allotment/maturity dates (ISO, blank if not a full date),
  fund managers, expense ratio, exit load, custodian, auditor, registrar and listing.
- `scheme_isins.csv` maps `mf_id` to every ISIN in the document.
- `scheme_amfi_codes.csv` maps `mf_id` to the AMFI scheme codes (the ones used in NAV files).

Rebuild with `git lfs pull && make schemes.csv`.

## Portfolio Holdings

Month-end portfolio holdings for every scheme, parsed from the XLS/XLSX monthly portfolio
disclosures that each AMC publishes on its own website. The AMC list comes from AMFI.

- `src/portfolio/amcs/<amc>.py` lists every monthly portfolio file an AMC serves.
- `portfolio/manifest/<amc>.csv` records each downloaded file (period, URL, sha256).
- Raw files are not kept in git. The `Portfolio Disclosures` workflow archives them as
  `raw-<amc>` release assets (one tar.gz per year) and keeps parsed holdings as
  `<amc>.csv.zst` on the `holdings` release.
- Dated releases carry `portfolio.db.zst`, a SQLite database:

```sql
schemes  (scheme_id, amc, name)
holdings (scheme_id, period, as_on, section, subsection, name, isin,
          industry_rating, quantity, market_value_lakh, pct_nav, ytm)
files    (amc, period, filename, url, scheme, sha256, size, fetched)
```

Scheme names are as printed in the AMC's sheet; they are not yet mapped to AMFI scheme codes.
Hedged schemes (arbitrage, equity savings) legitimately do not sum to 100% of NAV.

To try an AMC locally (downloads a single month into the gitignored `raw/`):

```bash
make portfolio AMC=ppfas
```

## Kuvera

Simple dataset containing a mapping between Kuvera's Mutual Fund IDs and their ISINs.
Data is contained in `data.csv`.

## LFS

This repo uses Git LFS to store SSD XMLs.


## License

Licensed under the [MIT License](https://nemo.mit-license.org/). See LICENSE file for details.