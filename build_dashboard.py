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
    
    # Flag dynamically if price is >50% away from the all-player median
    median_val = medians.get(chip)
    is_anomaly = False
    if median_val is not None and median_val > 0:
        ratio = val / median_val
        if ratio < 0.5 or ratio > 1.5:
            is_anomaly = True

    flag = ' <span class="flag" title="Price is >50% away from the all-player median — verify manually">⚠️</span>' if is_anomaly else ""
    return f'<span class="price">${val:.2f}</span>{flag}'


def build_price_table(latest, int_medians, int_averages, ind_medians, ind_averages, all_medians, all_averages):
    if not latest:
        return "<p>No data yet. Run the scraper first.</p>"

    # Separate providers
    int_sites = [site for site in latest if site["site_id"] not in ["neysa", "e2e"]]
    ind_sites = [site for site in latest if site["site_id"] in ["neysa", "e2e"]]

    # Header row
    header_chips = "".join(
        f'<th><span class="chip-badge" style="background:{CHIP_STYLES[c]["bg"]}; color:{CHIP_STYLES[c]["text"]}; border: 1px solid {CHIP_STYLES[c]["border"]}">{c} SXM</span></th>'
        for c in CHIPS
    )
    header = f"<tr><th>Provider</th>{header_chips}</tr>"

    rows = ""

    # 1. International Providers Section
    rows += f"""<tr class="group-header-row"><td colspan="{len(CHIPS) + 1}"><strong>International Providers</strong></td></tr>"""
    for site in int_sites:
        cells = ""
        for chip in CHIPS:
            price = site["chips"].get(chip, {}).get("price_usd_per_hour")
            cells += f"<td>{format_price(price, chip, all_medians)}</td>"
        rows += f"""
        <tr>
          <td class="provider">
            <a href="{site['url']}" target="_blank">{site['site_name']}</a>
          </td>
          {cells}
        </tr>"""

    # 2. International Averages & Medians
    int_avg_cells = "".join(
        f"<td><strong>${int_averages[c]:.2f}</strong></td>" if int_averages[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    int_med_cells = "".join(
        f"<td><strong>${int_medians[c]:.2f}</strong></td>" if int_medians[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    rows += f"""
    <tr class="summary-row int-summary-row">
      <td class="provider"><strong>International Average</strong></td>
      {int_avg_cells}
    </tr>
    <tr class="summary-row int-summary-row">
      <td class="provider"><strong>International Median</strong></td>
      {int_med_cells}
    </tr>"""

    # Spacer row
    rows += f"""<tr class="table-spacer-row"><td colspan="{len(CHIPS) + 1}"></td></tr>"""
    # 3. Indian Providers Section
    rows += f"""<tr class="group-header-row"><td colspan="{len(CHIPS) + 1}"><strong>Indian Providers</strong></td></tr>"""
    for site in ind_sites:
        cells = ""
        for chip in CHIPS:
            price = site["chips"].get(chip, {}).get("price_usd_per_hour")
            cells += f"<td>{format_price(price, chip, all_medians)}</td>"
        rows += f"""
        <tr>
          <td class="provider">
            <a href="{site['url']}" target="_blank">{site['site_name']}</a>
          </td>
          {cells}
        </tr>"""

    # 4. Indian Averages & Medians (Soft Amber background)
    ind_avg_cells = "".join(
        f"<td><strong>${ind_averages[c]:.2f}</strong></td>" if ind_averages[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    ind_med_cells = "".join(
        f"<td><strong>${ind_medians[c]:.2f}</strong></td>" if ind_medians[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    rows += f"""
    <tr class="summary-row ind-summary-row">
      <td class="provider"><strong>Indian Average</strong></td>
      {ind_avg_cells}
    </tr>
    <tr class="summary-row ind-summary-row">
      <td class="provider"><strong>Indian Median</strong></td>
      {ind_med_cells}
    </tr>"""

    # Spacer row
    rows += f"""<tr class="table-spacer-row"><td colspan="{len(CHIPS) + 1}"></td></tr>"""
    # 5. Combined Total Averages & Medians (Distinct Blue background)
    all_avg_cells = "".join(
        f"<td><strong>${all_averages[c]:.2f}</strong></td>" if all_averages[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    all_med_cells = "".join(
        f"<td><strong>${all_medians[c]:.2f}</strong></td>" if all_medians[c] is not None else "<td><strong>—</strong></td>"
        for c in CHIPS
    )
    rows += f"""
    <tr class="summary-row all-summary-row">
      <td class="provider"><strong>Total Average (All)</strong></td>
      {all_avg_cells}
    </tr>
    <tr class="summary-row all-summary-row">
      <td class="provider"><strong>Total Median (All)</strong></td>
      {all_med_cells}
    </tr>"""

    return f'<table id="pricingTable"><thead>{header}</thead><tbody>{rows}</tbody></table>'


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
        from datetime import timezone, timedelta
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Convert to IST (UTC + 5:30)
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        ist_dt = dt.astimezone(ist_tz)
        return ist_dt.strftime("%B %d, %Y at %I:%M %p IST")
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
    # Separate providers
    int_sites = [site for site in latest if site["site_id"] not in ["neysa", "e2e"]]
    ind_sites = [site for site in latest if site["site_id"] in ["neysa", "e2e"]]

    # Helper function to calculate stats
    def calc_stats(sites):
        prices_by_chip = {c: [] for c in CHIPS}
        for site in sites:
            for c in CHIPS:
                val = site["chips"].get(c, {}).get("price_usd_per_hour")
                if val is not None:
                    prices_by_chip[c].append(val)
        
        meds = {}
        avgs = {}
        for c in CHIPS:
            p_list = prices_by_chip[c]
            if p_list:
                meds[c] = statistics.median(p_list)
                avgs[c] = statistics.mean(p_list)
            else:
                meds[c] = None
                avgs[c] = None
        return meds, avgs

    int_medians, int_averages = calc_stats(int_sites)
    ind_medians, ind_averages = calc_stats(ind_sites)
    all_medians, all_averages = calc_stats(latest)

    table_html = build_price_table(
        latest, 
        int_medians, int_averages, 
        ind_medians, ind_averages, 
        all_medians, all_averages
    )
    labels_js, datasets_js = build_history_chart_data(history)
    last_updated = get_last_updated(latest)
    flagged_html = build_flagged_section(latest, all_medians)

    show_chart = "true" if history else "false"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GPU-as-a-Service Pricing Tracker</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #f9f9f8;
      --surface: #ffffff;
      --surface-hover: #f4f4f2;
      --border: #e8e8e6;
      --border-hover: #e0e0de;
      --text: #1a1a1a;
      --muted: #555552;
      --accent: #1a1a1a;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 3rem 2rem;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      letter-spacing: -0.01em;
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
    tr.group-header-row td {{
      background-color: var(--bg);
      color: var(--text);
      font-weight: 700;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.8rem 1.5rem;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
    }}
    tr.table-spacer-row td {{
      height: 24px;
      padding: 0;
      background-color: var(--bg);
      border: none;
    }}
    tr.summary-row td {{
      font-weight: 600;
      border-top: 1px solid var(--border);
    }}
    tr.int-summary-row td {{
      background-color: #f0fdf4; /* soft light green */
      color: #166534;
      border-top: 1px solid #dcfce7;
    }}
    tr.int-summary-row:hover td {{
      background-color: #dcfce7;
    }}
    tr.ind-summary-row td {{
      background-color: #fffbeb;
      color: #78350f;
      border-top: 1px solid #fef3c7;
    }}
    tr.ind-summary-row:hover td {{
      background-color: #fef3c7;
    }}
    tr.all-summary-row td {{
      background-color: #eff6ff;
      color: #1e40af;
      font-weight: 700;
      border-top: 2px solid #bfdbfe;
      border-bottom: 2px solid #bfdbfe;
    }}
    tr.all-summary-row:hover td {{
      background-color: #dbeafe;
    }}
    .table-header-actions {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 3rem 0 1rem;
    }}
    .btn-copy {{
      background-color: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 0.5rem 1rem;
      border-radius: 6px;
      font-family: 'Outfit', sans-serif;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: background-color 0.2s, border-color 0.2s;
    }}
    .btn-copy:hover {{
      background-color: var(--surface-hover);
      border-color: var(--border-hover);
    }}
    .btn-copy.btn-success {{
      background-color: #059669;
      color: #ffffff;
      border-color: #059669;
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

  <div class="table-header-actions">
    <p class="section-title">Current Prices (USD / hr)</p>
    <button id="copyTableBtn" onclick="copyTableToClipboard()" class="btn-copy">Copy to Excel</button>
  </div>
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
  function copyTableToClipboard() {{
    const table = document.getElementById("pricingTable");
    if (!table) return;

    let tsv = "";
    for (let row of table.rows) {{
      let rowData = [];
      for (let cell of row.cells) {{
        let text = cell.innerText.replace(/⚠️/g, "").trim();
        rowData.push(text);
      }}
      tsv += rowData.join("\t") + "\n";
    }}

    const tableHtml = table.outerHTML;
    const textBlob = new Blob([tsv], {{ type: 'text/plain' }});
    const htmlBlob = new Blob([tableHtml], {{ type: 'text/html' }});

    const data = [new ClipboardItem({{
      'text/plain': textBlob,
      'text/html': htmlBlob
    }})];

    navigator.clipboard.write(data).then(() => {{
      const btn = document.getElementById("copyTableBtn");
      const originalText = btn.innerText;
      btn.innerText = "✓ Copied!";
      btn.classList.add("btn-success");
      setTimeout(() => {{
        btn.innerText = originalText;
        btn.classList.remove("btn-success");
      }}, 2000);
    }}).catch(err => {{
      console.error("Failed to copy table: ", err);
      navigator.clipboard.writeText(tsv).then(() => {{
        const btn = document.getElementById("copyTableBtn");
        btn.innerText = "✓ Copied (Text)!";
        setTimeout(() => {{ btn.innerText = "Copy to Excel"; }}, 2000);
      }});
    }});
  }}

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
