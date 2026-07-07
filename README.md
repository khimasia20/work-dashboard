# Portfolio Dashboard

A Vercel-ready Python app for uploading a brokerage positions CSV, enriching holdings with live data from `yfinance`, viewing a portfolio dashboard, and exporting the same dashboard as a PDF.

## Features

- Upload brokerage position CSVs similar to the Schwab/Fidelity-style export in `ZARING FOUNDATION-Positions-2026-07-07-082636.csv`
- Parses quantity, market value, cost basis, gain/loss, dividend yield, and account weight
- Fetches current price, analyst average target price, potential upside, trailing PE, and forward PE from `yfinance`
- Shows total market value, cost basis, P/L, portfolio dividend yield, and weighted upside
- Exports the current dashboard to PDF

## Local Development

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python api/index.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Deploy To Vercel

```powershell
vercel
```

The app is configured by `vercel.json` to run `api/index.py` with the Vercel Python runtime.

## Notes

Market data comes from Yahoo Finance through `yfinance`, so fields may be missing for some tickers and values can change during market hours.
