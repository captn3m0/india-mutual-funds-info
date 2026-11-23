# Mutual Funds Information

:warning: This repository used to be at `captn3m0/kuvera-mutual-funds-lookup`. Since now it contains more than just the Kuvera Identifiers, I've renamed it to `captn3m0/india-mutual-funds-info`.

SEBI Mutual Fund Identifiers, and SSD parsing are WIP. Stay tuned. All data will be published in CSV/SQLite/HTTP-API formats, with standard identifiers (ISINs/SEBI-IDs).

## Mutual Funds Information

`amfi_funds.csv` contains AMC_ID,MF_ID,MF_NAME. All identifiers are AMFI Identifiers here.

## Portfolio Holdings

Month-end portfolio holdings for every scheme, parsed from the XLS/XLSX monthly portfolio
disclosures that each AMC publishes on its own website. The AMC list comes from AMFI.

- `src/portfolio/amcs/<amc>.py` lists every monthly portfolio file an AMC serves.
- `portfolio/manifest/<amc>.csv` records each downloaded file (period, URL, sha256).
- Raw files are not kept in git. The `Portfolio Disclosures` workflow archives them as
  `raw-<amc>` release assets (one tar per period) and keeps parsed holdings as
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