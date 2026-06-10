"""
build_dashboard.py
Reads data/latest.json and data/history.json
Generates docs/index.html — served by GitHub Pages
"""

import json
from pathlib import Path
from datetime import datetime
import statistics

CHIPS = ["H100", "H200", "B200", "B300"]
CHIP_COLORS = {
    "H100": "#2563eb",  # Premium blue
    "H200": "#ea580c",  # Orange
    "B200": "#16a34a",  # Green
    "B300": "#e11d48",  # Rose
}
CHIP_STYLES = {
    "H100": {"bg": "#eff6ff", "text": "#1e40af", "border": "#bfdbfe"},
    "H200": {"bg": "#fff7ed", "text": "#9a3412", "border": "#ffedd5"},
    "B200": {"bg": "#ecfdf5", "text": "#065f46", "border": "#d1fae5"},
    "B300": {"bg": "#fff1f2", "text": "#9f1239", "border": "#ffe4e6"},
}


def load_data():
    latest_path = Path("data/latest.json")
    history_path = Path("data/history.json")

    latest = json.loads(latest_path.read_text()) if latest_path.exists() else []
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    return latest, history


def format_price(val, chip, medians):
    if val is None:
        return '<span class="na">—</span>'
    
    # Flag dynamically if price is >50% away from the median
    median_val = medians.get(chip)
    is_anomaly = False
    if median_val is not None and median_val > 0:
        ratio = val / median_val
        if ratio < 0.5 or ratio > 1.5:
            is_anomaly = True

    flag = ' <span class="flag" title="Price is >50% away from the median — verify manually">⚠️</span>' if is_anomaly else ""
    return f'<span class="price">${val:.2f}</span>{flag}'


def build_price_table(latest, medians, averages):
    if not latest:
        return "<p>No data yet. Run the scraper first.</p>"

    # Header row
    header_chips = "".join(
        f'<th><span class="chip-badge" style="background:{CHIP_STYLES[c]["bg"]}; color:{CHIP_STYLES[c]["text"]}; border: 1px solid {CHIP_STYLES[c]["border"]}">{c} SXM</span></th>'
        for c in CHIPS
    )
    header = f"<tr><th>Provider</th>{header_chips}</tr>"

    rows = ""
    for site in latest:
        cells = ""
        for chip in CHIPS:
            price = site["chips"].get(chip, {}).get("price_usd_per_hour")
            cells += f"<td>{format_price(price, chip, medians)}</td>"
        rows += f"""
        <tr>
          <td class="provider">
            <a href="{site['url']}" target="_blank">{site['site_name']}</a>
          </td>
          {cells}
        </tr>"""

    # Add Average Row
    avg_cells = "".join(
        f"<td><strong>${averages[c]:.2f}</strong></td>" if averages[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    rows += f"""
    <tr class="summary-row">
      <td class="provider"><strong>Average</strong></td>
      {avg_cells}
    </tr>"""

    # Add Median Row
    med_cells = "".join(
        f"<td><strong>${medians[c]:.2f}</strong></td>" if medians[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    rows += f"""
    <tr class="summary-row">
      <td class="provider"><strong>Median</strong></td>
      {med_cells}
    </tr>"""

    return f"<table><thead>{header}</thead><tbody>{rows}</tbody></table>"


def build_history_chart_data(history):
    """Build JS-friendly dataset for Chart.js trend lines."""
    # Collect all run timestamps
    labels = [h["run_at"][:10] for h in history]  # YYYY-MM-DD

    # For each chip, collect lowest price seen across all providers per run
    datasets = []
    for chip in CHIPS:
        prices = []
        for run in history:
            run_prices = []
            for site in run["results"]:
                val = site["chips"].get(chip, {}).get("price_usd_per_hour")
                if val is not None:
                    run_prices.append(val)
            prices.append(min(run_prices) if run_prices else None)

        datasets.append({
            "label": f"{chip} SXM (lowest)",
            "data": prices,
            "borderColor": CHIP_COLORS[chip],
            "backgroundColor": CHIP_COLORS[chip] + "33",
            "tension": 0.3,
            "spanGaps": True,
        })

    return json.dumps(labels), json.dumps(datasets)


def get_last_updated(latest):
    if not latest:
        return "Never"
    ts = latest[0].get("scraped_at", "")
    if ts:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y at %H:%M UTC")
    return "Unknown"


def build_flagged_section(latest, medians):
    flagged = []
    for site in latest:
        for chip in CHIPS:
            price = site["chips"].get(chip, {}).get("price_usd_per_hour")
            if price is not None:
                median_val = medians.get(chip)
                if median_val is not None and median_val > 0:
                    ratio = price / median_val
                    if ratio < 0.5 or ratio > 1.5:
                        flagged.append(
                            f"<li><strong>{site['site_name']}</strong> — {chip} SXM: "
                            f"${price:.2f}/hr (unusual rate: {ratio*100:.1f}% of median ${median_val:.2f}/hr)</li>"
                        )
    if not flagged:
        return '<p class="all-good">✅ All extracted prices are within expected ranges.</p>'
    return "<ul class='flagged-list'>" + "".join(flagged) + "</ul>"


def generate_html(latest, history):
    # Calculate medians and averages for each chip
    chip_prices = {c: [] for c in CHIPS}
    for site in latest:
        for c in CHIPS:
            val = site["chips"].get(c, {}).get("price_usd_per_hour")
            if val is not None:
                chip_prices[c].append(val)

    medians = {}
    averages = {}
    for c in CHIPS:
        prices = chip_prices[c]
        if prices:
            medians[c] = statistics.median(prices)
            averages[c] = statistics.mean(prices)
        else:
            medians[c] = None
            averages[c] = None

    table_html = build_price_table(latest, medians, averages)
    labels_js, datasets_js = build_history_chart_data(history)
    last_updated = get_last_updated(latest)
    flagged_html = build_flagged_section(latest, medians)

    show_chart = "true" if history else "false"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GPU-as-a-Service Pricing Tracker</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #f8fafc;
      --surface: #ffffff;
      --surface-hover: #f1f5f9;
      --border: #e2e8f0;
      --border-hover: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 3rem 2rem;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 3rem;
      flex-wrap: wrap;
      gap: 1.5rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 2rem;
    }}
    h1 {{
      font-size: 2.2rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.02em;
    }}
    h1 span {{
      color: var(--accent);
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 0.95rem;
      margin-top: 0.5rem;
      font-weight: 400;
    }}
    .last-updated {{
      text-align: right;
      font-size: 0.85rem;
      color: var(--muted);
    }}
    .last-updated strong {{
      color: var(--text);
      font-size: 0.95rem;
      display: block;
      margin-top: 0.25rem;
    }}
    .section-title {{
      font-size: 0.85rem;
      font-weight: 600;
      margin: 3rem 0 1rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}
    /* Card Styles */
    .card-wrap {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
      overflow: hidden;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .card-wrap:hover {{
      border-color: var(--border-hover);
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
    }}
    /* Table */
    .table-wrap {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      padding: 1.1rem 1.5rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      background: #f8fafc;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr {{ transition: background-color 0.2s ease; }}
    tr:hover td {{
      background-color: var(--surface-hover);
    }}
    tr.summary-row td {{
      background-color: #f8fafc;
      border-top: 2px solid var(--border);
    }}
    tr.summary-row:hover td {{
      background-color: #f1f5f9;
    }}
    .provider a {{
      color: var(--text);
      text-decoration: none;
      font-weight: 600;
      font-size: 1rem;
      transition: color 0.2s ease;
      display: inline-block;
    }}
    .provider a:hover {{
      color: var(--accent);
    }}
    .price {{
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      font-size: 1.05rem;
    }}
    .na {{
      color: rgba(71, 85, 105, 0.3);
      font-weight: 400;
    }}
    .chip-badge {{
      display: inline-block;
      padding: 0.25em 0.75em;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    .flag {{
      cursor: help;
      margin-left: 0.25rem;
    }}
    /* Chart */
    .chart-wrap {{
      padding: 2rem;
    }}
    /* Sanity section */
    .sanity-wrap {{
      padding: 1.5rem 2rem;
    }}
    .all-good {{
      color: #059669;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 500;
    }}
    .flagged-list {{
      padding-left: 1.2rem;
    }}
    .flagged-list li {{
      margin-bottom: 0.5rem;
      color: #d97706;
    }}
    /* Footer */
    footer {{
      margin-top: 5rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.85rem;
      text-align: center;
      line-height: 1.6;
    }}
    footer a {{
      color: var(--muted);
      text-decoration: underline;
      transition: color 0.2s;
    }}
    footer a:hover {{
      color: var(--text);
    }}
  </style>
</head>
<body>

<div class="container">
  <header>
    <div>
      <h1>GPU-as-a-Service <span>Pricing Tracker</span></h1>
      <div class="subtitle">NVIDIA H100 · H200 · B200 · B300 · SXM variants · On-demand pricing · USD/hr</div>
    </div>
    <div class="last-updated">
      Last updated
      <strong>{last_updated}</strong>
    </div>
  </header>

  <p class="section-title">Current Prices (USD / hr)</p>
  <div class="card-wrap table-wrap">
    {table_html}
  </div>

  <p class="section-title">Price Trends — Lowest Available per Chip</p>
  <div class="card-wrap chart-wrap">
    <canvas id="trendChart" height="100"></canvas>
  </div>

  <p class="section-title">Sanity Check — Flagged Prices</p>
  <div class="card-wrap sanity-wrap">
    {flagged_html}
  </div>

  <footer>
    Updated automatically every 7 days via GitHub Actions ·
    Powered by Playwright + Llama 3.3 70B (Groq) ·
    <a href="https://github.com" target="_blank">View source</a>
  </footer>
</div>

<script>
  const showChart = {show_chart};
  if (showChart) {{
    const ctx = document.getElementById("trendChart").getContext("2d");
    new Chart(ctx, {{
      type: "line",
      data: {{
        labels: {labels_js},
        datasets: {datasets_js},
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{
            labels: {{
              color: "#0f172a",
              font: {{ family: "'Outfit', sans-serif", size: 12, weight: 500 }}
            }}
          }}
        }},
        scales: {{
          x: {{
            ticks: {{ color: "#475569", font: {{ family: "'Outfit', sans-serif" }} }},
            grid: {{ color: "rgba(0, 0, 0, 0.05)" }}
          }},
          y: {{
            ticks: {{
              color: "#475569",
              font: {{ family: "'Outfit', sans-serif" }},
              callback: v => "$" + v.toFixed(2)
            }},
            grid: {{ color: "rgba(0, 0, 0, 0.05)" }},
            title: {{
              display: true,
              text: "USD / hr",
              color: "#475569",
              font: {{ family: "'Outfit', sans-serif", weight: 600 }}
            }}
          }}
        }}
      }}
    }});
  }} else {{
    document.getElementById("trendChart").parentElement.innerHTML =
      "<p style='color:#64748b;text-align:center;padding:2rem'>Trend chart will appear after the second run.</p>";
  }}
</script>

</body>
</html>
"""


def main():
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    latest, history = load_data()
    html = generate_html(latest, history)

    out = docs_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {out}")


if __name__ == "__main__":
    main()
