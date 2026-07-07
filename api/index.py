from __future__ import annotations

import csv
import io
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import yfinance as yf
from flask import Flask, jsonify, make_response, render_template_string, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

app = Flask(__name__)


HTML = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Portfolio Dashboard</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fb;
        --panel: #ffffff;
        --ink: #14213d;
        --muted: #637083;
        --line: #dce3ee;
        --accent: #0f766e;
        --accent-2: #1d4ed8;
        --danger: #b42318;
        --good: #087443;
        --warn: #a15c07;
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        background: var(--bg);
        color: var(--ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      header {
        background: #ffffff;
        border-bottom: 1px solid var(--line);
      }

      .wrap {
        width: min(1280px, calc(100vw - 32px));
        margin: 0 auto;
      }

      .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 76px;
        gap: 16px;
      }

      h1 {
        margin: 0;
        font-size: clamp(24px, 3vw, 34px);
        line-height: 1.05;
        letter-spacing: 0;
      }

      .subtle {
        color: var(--muted);
        font-size: 14px;
        margin-top: 6px;
      }

      main {
        padding: 24px 0 40px;
      }

      .upload {
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 12px;
        align-items: center;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px;
      }

      input[type="file"] {
        width: 100%;
        min-height: 42px;
        border: 1px dashed #a9b6c8;
        border-radius: 6px;
        padding: 9px;
        background: #fbfcff;
        color: var(--muted);
      }

      button {
        min-height: 42px;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 0 16px;
        background: var(--accent);
        color: #fff;
        font-weight: 700;
        cursor: pointer;
      }

      button.secondary {
        background: #ffffff;
        border-color: var(--line);
        color: var(--ink);
      }

      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      .status {
        min-height: 28px;
        color: var(--muted);
        font-size: 14px;
        padding: 12px 2px 2px;
      }

      .summary {
        display: grid;
        grid-template-columns: repeat(5, minmax(160px, 1fr));
        gap: 12px;
        margin: 18px 0;
      }

      .metric {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px;
        min-height: 96px;
      }

      .metric span {
        display: block;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .metric strong {
        display: block;
        margin-top: 10px;
        font-size: 22px;
        line-height: 1.15;
      }

      .table-shell {
        overflow: auto;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
      }

      table {
        width: 100%;
        min-width: 1120px;
        border-collapse: collapse;
      }

      th, td {
        padding: 11px 12px;
        border-bottom: 1px solid var(--line);
        text-align: right;
        white-space: nowrap;
        font-size: 14px;
      }

      th {
        position: sticky;
        top: 0;
        z-index: 1;
        background: #eef3f8;
        color: #2f3b4c;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      td:first-child, th:first-child,
      td:nth-child(2), th:nth-child(2) {
        text-align: left;
      }

      tr:last-child td { border-bottom: 0; }
      .good { color: var(--good); font-weight: 700; }
      .bad { color: var(--danger); font-weight: 700; }
      .warn { color: var(--warn); font-weight: 700; }
      .empty {
        display: grid;
        min-height: 260px;
        place-items: center;
        color: var(--muted);
        text-align: center;
      }

      @media (max-width: 900px) {
        .topbar, .upload {
          grid-template-columns: 1fr;
          align-items: stretch;
        }

        .topbar {
          display: block;
          padding: 18px 0;
        }

        .summary {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      @media (max-width: 560px) {
        .wrap {
          width: min(100vw - 20px, 1280px);
        }

        .summary {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <div class="wrap topbar">
        <div>
          <h1>Portfolio Dashboard</h1>
          <div class="subtle">Upload positions, refresh live Yahoo Finance data, and export a PDF snapshot.</div>
        </div>
      </div>
    </header>

    <main class="wrap">
      <form id="uploadForm" class="upload">
        <input id="csvFile" name="file" type="file" accept=".csv,text/csv" required>
        <button id="analyzeBtn" type="submit">Analyze CSV</button>
        <button id="pdfBtn" class="secondary" type="button" disabled>Export PDF</button>
      </form>
      <div id="status" class="status"></div>

      <section id="summary" class="summary" hidden></section>

      <section class="table-shell">
        <div id="empty" class="empty">Upload a brokerage positions CSV to build your dashboard.</div>
        <table id="table" hidden>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Avg Cost</th>
              <th>Current</th>
              <th>Market Value</th>
              <th>Cost Basis</th>
              <th>P/L</th>
              <th>P/L %</th>
              <th>Div Yield</th>
              <th>Avg Target</th>
              <th>Upside</th>
              <th>Trailing PE</th>
              <th>Forward PE</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </section>
    </main>

    <script>
      const form = document.getElementById("uploadForm");
      const fileInput = document.getElementById("csvFile");
      const analyzeBtn = document.getElementById("analyzeBtn");
      const pdfBtn = document.getElementById("pdfBtn");
      const statusEl = document.getElementById("status");
      const summaryEl = document.getElementById("summary");
      const table = document.getElementById("table");
      const tbody = table.querySelector("tbody");
      const empty = document.getElementById("empty");
      let latestDashboard = null;

      const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
      const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

      function fmtMoney(value) {
        return value === null || value === undefined ? "N/A" : money.format(value);
      }

      function fmtNumber(value) {
        return value === null || value === undefined ? "N/A" : number.format(value);
      }

      function fmtPct(value) {
        return value === null || value === undefined ? "N/A" : `${number.format(value)}%`;
      }

      function signedClass(value) {
        if (value === null || value === undefined) return "";
        if (value > 0) return "good";
        if (value < 0) return "bad";
        return "";
      }

      function renderSummary(summary) {
        const metrics = [
          ["Market Value", fmtMoney(summary.total_market_value)],
          ["Cost Basis", fmtMoney(summary.total_cost_basis)],
          ["Total P/L", fmtMoney(summary.total_pl), signedClass(summary.total_pl)],
          ["Portfolio Yield", fmtPct(summary.weighted_dividend_yield)],
          ["Weighted Upside", fmtPct(summary.weighted_upside), summary.weighted_upside >= 0 ? "good" : "bad"]
        ];
        summaryEl.innerHTML = metrics.map(([label, value, cls]) => `
          <article class="metric">
            <span>${label}</span>
            <strong class="${cls || ""}">${value}</strong>
          </article>
        `).join("");
        summaryEl.hidden = false;
      }

      function renderRows(rows) {
        tbody.innerHTML = rows.map(row => `
          <tr>
            <td><strong>${row.symbol}</strong></td>
            <td>${row.description || ""}</td>
            <td>${fmtNumber(row.quantity)}</td>
            <td>${fmtMoney(row.average_cost)}</td>
            <td>${fmtMoney(row.current_price)}</td>
            <td>${fmtMoney(row.market_value)}</td>
            <td>${fmtMoney(row.cost_basis)}</td>
            <td class="${signedClass(row.pl)}">${fmtMoney(row.pl)}</td>
            <td class="${signedClass(row.pl_percent)}">${fmtPct(row.pl_percent)}</td>
            <td>${fmtPct(row.dividend_yield)}</td>
            <td>${fmtMoney(row.target_mean_price)}</td>
            <td class="${signedClass(row.potential_upside)}">${fmtPct(row.potential_upside)}</td>
            <td>${fmtNumber(row.trailing_pe)}</td>
            <td>${fmtNumber(row.forward_pe)}</td>
          </tr>
        `).join("");
        table.hidden = false;
        empty.hidden = true;
      }

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!fileInput.files.length) return;

        const data = new FormData();
        data.append("file", fileInput.files[0]);
        analyzeBtn.disabled = true;
        pdfBtn.disabled = true;
        statusEl.textContent = "Reading positions and fetching live market data...";

        try {
          const response = await fetch("/api/analyze", { method: "POST", body: data });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || "Unable to analyze CSV.");
          latestDashboard = payload;
          renderSummary(payload.summary);
          renderRows(payload.rows);
          pdfBtn.disabled = false;
          statusEl.textContent = `Loaded ${payload.rows.length} positions. Data refreshed ${payload.generated_at}.`;
        } catch (error) {
          statusEl.textContent = error.message;
        } finally {
          analyzeBtn.disabled = false;
        }
      });

      pdfBtn.addEventListener("click", async () => {
        if (!latestDashboard) return;
        pdfBtn.disabled = true;
        statusEl.textContent = "Generating PDF...";

        try {
          const response = await fetch("/api/pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(latestDashboard)
          });
          if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || "Unable to generate PDF.");
          }
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = "portfolio-dashboard.pdf";
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(url);
          statusEl.textContent = "PDF exported.";
        } catch (error) {
          statusEl.textContent = error.message;
        } finally {
          pdfBtn.disabled = false;
        }
      });
    </script>
  </body>
</html>
"""


def parse_decimal(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "--"}:
        return None
    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[$,%()]", "", text).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if is_negative else number


def normalize_percent(value: Any) -> float | None:
    parsed = parse_decimal(value)
    if parsed is None:
        return None
    return parsed * 100 if abs(parsed) <= 1 and "%" not in str(value) else parsed


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip(): value for key, value in row.items() if key and str(key).strip()}


def parse_positions(file_bytes: bytes) -> list[dict[str, Any]]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    raw_rows = list(csv.reader(io.StringIO(text)))
    header_index = next(
        (index for index, row in enumerate(raw_rows) if row and row[0].strip().lower() == "symbol"),
        None,
    )
    if header_index is None:
        raise ValueError("Could not find a Symbol header row in the CSV.")

    csv_text = "\n".join(",".join(csv_escape(cell) for cell in row) for row in raw_rows[header_index:])
    reader = csv.DictReader(io.StringIO(csv_text))
    positions: list[dict[str, Any]] = []

    for raw in reader:
        row = clean_row(raw)
        symbol = str(row.get("Symbol", "")).strip().upper()
        quantity = parse_decimal(row.get("Qty (Quantity)"))
        if not symbol or symbol == "CASH" or quantity is None or quantity == 0:
            continue

        cost_basis = parse_decimal(row.get("Cost Basis"))
        market_value = parse_decimal(row.get("Mkt Val (Market Value)"))
        price = parse_decimal(row.get("Price"))
        pl = parse_decimal(row.get("Gain $ (Gain/Loss $)"))
        pl_percent = normalize_percent(row.get("Gain % (Gain/Loss %)"))
        dividend_yield = normalize_percent(row.get("Div Yld (Dividend Yield)"))

        positions.append(
            {
                "symbol": symbol.replace(".", "-"),
                "description": str(row.get("Description", "")).strip(),
                "quantity": quantity,
                "uploaded_price": price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "pl": pl,
                "pl_percent": pl_percent,
                "uploaded_dividend_yield": dividend_yield,
                "account_percent": normalize_percent(row.get("% of Acct (% of Account)")),
            }
        )

    if not positions:
        raise ValueError("No equity positions were found in the CSV.")
    return positions


def csv_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    if any(char in text for char in [",", '"', "\n"]):
        return '"' + text.replace('"', '""') + '"'
    return text


def finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def fetch_current_prices(symbols: list[str]) -> dict[str, float]:
    try:
        data = yf.download(
            tickers=" ".join(symbols),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
        )
    except Exception:
        return {}

    prices: dict[str, float] = {}
    for symbol in symbols:
        try:
            if len(symbols) == 1:
                close = data["Close"].dropna()
            else:
                close = data[(symbol, "Close")].dropna()
            if not close.empty:
                value = finite(close.iloc[-1])
                if value is not None:
                    prices[symbol] = value
        except Exception:
            continue
    return prices


def fetch_fundamentals(symbol: str) -> dict[str, float | None]:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
    except Exception:
        return {}

    dividend_yield = finite(info.get("dividendYield"))
    if dividend_yield is not None and dividend_yield <= 1:
        dividend_yield *= 100

    return {
        "target_mean_price": finite(info.get("targetMeanPrice")),
        "dividend_yield": dividend_yield,
        "trailing_pe": finite(info.get("trailingPE")),
        "forward_pe": finite(info.get("forwardPE")),
    }


def enrich_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batch_prices = fetch_current_prices([row["symbol"] for row in positions])
    quotes: dict[str, dict[str, float | None]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(positions))) as executor:
        futures = {executor.submit(fetch_fundamentals, row["symbol"]): row["symbol"] for row in positions}
        for future in as_completed(futures):
            quotes[futures[future]] = future.result()

    enriched = []
    for row in positions:
        quote = quotes.get(row["symbol"], {})
        current_price = batch_prices.get(row["symbol"]) or row.get("uploaded_price")
        market_value = row.get("market_value")
        if current_price is not None:
            market_value = current_price * row["quantity"]

        cost_basis = row.get("cost_basis")
        average_cost = cost_basis / row["quantity"] if cost_basis is not None else None
        pl = market_value - cost_basis if market_value is not None and cost_basis is not None else row.get("pl")
        pl_percent = (pl / cost_basis * 100) if pl is not None and cost_basis not in (None, 0) else row.get("pl_percent")
        target = quote.get("target_mean_price")
        upside = ((target - current_price) / current_price * 100) if target and current_price else None

        enriched.append(
            {
                "symbol": row["symbol"],
                "description": row["description"],
                "quantity": round(row["quantity"], 4),
                "average_cost": round_or_none(average_cost),
                "current_price": round_or_none(current_price),
                "market_value": round_or_none(market_value),
                "cost_basis": round_or_none(cost_basis),
                "pl": round_or_none(pl),
                "pl_percent": round_or_none(pl_percent),
                "dividend_yield": round_or_none(quote.get("dividend_yield") or row.get("uploaded_dividend_yield")),
                "target_mean_price": round_or_none(target),
                "potential_upside": round_or_none(upside),
                "trailing_pe": round_or_none(quote.get("trailing_pe")),
                "forward_pe": round_or_none(quote.get("forward_pe")),
            }
        )

    return enriched


def round_or_none(value: Any, places: int = 2) -> float | None:
    number = finite(value)
    return round(number, places) if number is not None else None


def weighted_average(rows: list[dict[str, Any]], field: str) -> float | None:
    total_value = sum(row["market_value"] or 0 for row in rows)
    if total_value == 0:
        return None
    weighted = 0.0
    weight_total = 0.0
    for row in rows:
        value = row.get(field)
        market_value = row.get("market_value")
        if value is None or market_value is None:
            continue
        weighted += value * market_value
        weight_total += market_value
    if weight_total == 0:
        return None
    return round(weighted / weight_total, 2)


def summarize(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    total_market_value = sum(row["market_value"] or 0 for row in rows)
    total_cost_basis = sum(row["cost_basis"] or 0 for row in rows)
    total_pl = total_market_value - total_cost_basis if total_cost_basis else None

    return {
        "total_market_value": round_or_none(total_market_value),
        "total_cost_basis": round_or_none(total_cost_basis),
        "total_pl": round_or_none(total_pl),
        "total_pl_percent": round_or_none(total_pl / total_cost_basis * 100 if total_pl is not None and total_cost_basis else None),
        "weighted_dividend_yield": weighted_average(rows, "dividend_yield"),
        "weighted_upside": weighted_average(rows, "potential_upside"),
    }


@app.get("/")
def home():
    return render_template_string(HTML)


@app.post("/api/analyze")
def analyze():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Please upload a CSV file."}), 400
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported."}), 400

    try:
        positions = parse_positions(uploaded.read())
        rows = enrich_positions(positions)
        return jsonify(
            {
                "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "rows": rows,
                "summary": summarize(rows),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Failed to analyze portfolio")
        return jsonify({"error": f"Failed to analyze portfolio: {exc}"}), 500


@app.post("/api/pdf")
def pdf():
    payload = request.get_json(silent=True) or {}
    rows = payload.get("rows") or []
    summary = payload.get("summary") or {}
    generated_at = payload.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if not rows:
        return jsonify({"error": "No dashboard rows were provided."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.35 * inch,
        leftMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Portfolio Dashboard", styles["Title"]),
        Paragraph(f"Generated {generated_at}", styles["Normal"]),
        Spacer(1, 0.12 * inch),
    ]

    summary_data = [
        ["Market Value", "Cost Basis", "Total P/L", "Portfolio Yield", "Weighted Upside"],
        [
            money(summary.get("total_market_value")),
            money(summary.get("total_cost_basis")),
            money(summary.get("total_pl")),
            pct(summary.get("weighted_dividend_yield")),
            pct(summary.get("weighted_upside")),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[1.9 * inch] * 5)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#26364a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d3e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.extend([summary_table, Spacer(1, 0.18 * inch)])

    table_data = [
        [
            "Symbol",
            "Qty",
            "Avg Cost",
            "Current",
            "Mkt Value",
            "Cost Basis",
            "P/L",
            "Div Yield",
            "Target",
            "Upside",
            "Trail PE",
            "Fwd PE",
        ]
    ]
    for row in rows:
        table_data.append(
            [
                row.get("symbol", ""),
                num(row.get("quantity")),
                money(row.get("average_cost")),
                money(row.get("current_price")),
                money(row.get("market_value")),
                money(row.get("cost_basis")),
                money(row.get("pl")),
                pct(row.get("dividend_yield")),
                money(row.get("target_mean_price")),
                pct(row.get("potential_upside")),
                num(row.get("trailing_pe")),
                num(row.get("forward_pe")),
            ]
        )

    dashboard_table = Table(table_data, repeatRows=1)
    dashboard_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7dee9")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(dashboard_table)
    doc.build(elements)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = 'attachment; filename="portfolio-dashboard.pdf"'
    return response


def money(value: Any) -> str:
    number = finite(value)
    return "N/A" if number is None else f"${number:,.2f}"


def pct(value: Any) -> str:
    number = finite(value)
    return "N/A" if number is None else f"{number:,.2f}%"


def num(value: Any) -> str:
    number = finite(value)
    return "N/A" if number is None else f"{number:,.2f}"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
