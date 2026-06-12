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
    price_class = "price outlier" if is_anomaly else "price"
    return f'<span class="{price_class}">${val:.2f}</span>{flag}'


def build_price_table(latest, int_medians, int_averages, ind_medians, ind_averages, all_medians, all_averages):
    if not latest:
        return "<p>No data yet. Run the scraper first.</p>"

    # Separate providers
    int_sites = [site for site in latest if site["site_id"] not in ["neysa", "e2e"]]
    ind_sites = [site for site in latest if site["site_id"] in ["neysa", "e2e"]]

    # Header row (plain text, no badges)
    header_chips = "".join(
        f'<th>{c} SXM</th>'
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
        f"<td>${int_averages[c]:.2f}</td>" if int_averages[c] is not None else "<td>—</td>"
        for c in CHIPS
    )
    int_med_cells = "".join(
        f"<td>${int_medians[c]:.2f}</td>" if int_medians[c] is not None else "<td>—</td>"
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
        f"<td>${ind_averages[c]:.2f}</td>" if ind_averages[c] is not None else "<td>—</td>"
        for c in CHIPS
    )
    ind_med_cells = "".join(
        f"<td>${ind_medians[c]:.2f}</td>" if ind_medians[c] is not None else "<td>—</td>"
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
        f"<td>${all_averages[c]:.2f}</td>" if all_averages[c] is not None else "<td>—</td>"
        for c in CHIPS
    )
    all_med_cells = "".join(
        f"<td>${all_medians[c]:.2f}</td>" if all_medians[c] is not None else "<td>—</td>"
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

    # For each chip, collect lowest clean price seen across all providers per run
    datasets = []
    for chip in CHIPS:
        prices = []
        for run in history:
            run_prices = []
            for site in run["results"]:
                val = site["chips"].get(chip, {}).get("price_usd_per_hour")
                if val is not None:
                    run_prices.append(val)
            
            if run_prices:
                run_median = statistics.median(run_prices)
                if run_median > 0:
                    clean_prices = [
                        p for p in run_prices 
                        if 0.5 * run_median <= p <= 1.5 * run_median
                    ]
                else:
                    clean_prices = run_prices
                
                prices.append(min(clean_prices) if clean_prices else None)
            else:
                prices.append(None)

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
    flagged_rows = ""
    for site in latest:
        for chip in CHIPS:
            price = site["chips"].get(chip, {}).get("price_usd_per_hour")
            if price is not None:
                median_val = medians.get(chip)
                if median_val is not None and median_val > 0:
                    ratio = price / median_val
                    if ratio < 0.5 or ratio > 1.5:
                        diff_pct = (ratio - 1) * 100
                        diff_str = f"+{diff_pct:.1f}%" if diff_pct > 0 else f"{diff_pct:.1f}%"
                        flagged_rows += f"""
                        <tr>
                          <td>{site['site_name']}</td>
                          <td>{chip} SXM</td>
                          <td class="flagged-price">${price:.2f}</td>
                          <td>${median_val:.2f}</td>
                          <td class="flagged-deviation">{diff_str}</td>
                        </tr>"""
    if not flagged_rows:
        return '<p class="all-good">✓ All extracted prices are within normal expected ranges.</p>'
    return f"""
    <table class="flagged-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>GPU Chip</th>
          <th>Scraped Price</th>
          <th>All-Player Median</th>
          <th>Deviation</th>
        </tr>
      </thead>
      <tbody>
        {flagged_rows}
      </tbody>
    </table>"""


def generate_html(latest, history):
    # Separate providers
    int_sites = [site for site in latest if site["site_id"] not in ["neysa", "e2e"]]
    ind_sites = [site for site in latest if site["site_id"] in ["neysa", "e2e"]]

    # 1. Calculate overall medians first (using all available prices, no filtering)
    all_prices_by_chip = {c: [] for c in CHIPS}
    for site in latest:
        for c in CHIPS:
            val = site["chips"].get(c, {}).get("price_usd_per_hour")
            if val is not None:
                all_prices_by_chip[c].append(val)
    
    all_medians = {}
    for c in CHIPS:
        p_list = all_prices_by_chip[c]
        all_medians[c] = statistics.median(p_list) if p_list else None

    # Helper function to calculate stats for a group of sites
    def calc_group_stats(sites, medians_ref):
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
                # Group median (no filtering)
                meds[c] = statistics.median(p_list)
                
                # Exclude pricing anomalies (>50% away from the overall median) for the average
                ref_med = medians_ref.get(c)
                if ref_med is not None and ref_med > 0:
                    filtered_p = [p for p in p_list if 0.5 * ref_med <= p <= 1.5 * ref_med]
                else:
                    filtered_p = p_list
                
                if filtered_p:
                    avgs[c] = statistics.mean(filtered_p)
                else:
                    avgs[c] = None
            else:
                meds[c] = None
                avgs[c] = None
        return meds, avgs

    int_medians, int_averages = calc_group_stats(int_sites, all_medians)
    ind_medians, ind_averages = calc_group_stats(ind_sites, all_medians)
    _, all_averages = calc_group_stats(latest, all_medians)

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
    .site-header {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem 2rem;
      margin-bottom: 2.5rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }}
    .header-main {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1.5rem;
    }}
    .brand-zone {{
      display: flex;
      align-items: center;
      gap: 1rem;
    }}
    .brand-logo {{
      background: #1a1a1a;
      color: #ffffff;
      font-size: 0.85rem;
      font-weight: 700;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .brand-details h1 {{
      font-size: 1.35rem;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.015em;
      line-height: 1.2;
      margin: 0;
    }}
    .subtitle-text {{
      color: var(--muted);
      font-size: 0.82rem;
      margin-top: 0.15rem;
    }}
    .header-meta {{
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      padding: 0.3rem 0.6rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 500;
      color: #166534;
    }}
    .status-dot {{
      width: 6px;
      height: 6px;
      background-color: #22c55e;
      border-radius: 50%;
      display: inline-block;
      animation: pulse-dot 2s infinite;
    }}
    @keyframes pulse-dot {{
      0% {{ transform: scale(0.95); opacity: 0.8; }}
      50% {{ transform: scale(1.15); opacity: 1; }}
      100% {{ transform: scale(0.95); opacity: 0.8; }}
    }}
    .update-badge {{
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 0.3rem 0.6rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 500;
      color: var(--muted);
    }}
    .header-sub {{
      border-top: 1px solid var(--border);
      margin-top: 1rem;
      padding-top: 0.75rem;
      font-size: 0.78rem;
      font-weight: 500;
      color: var(--muted);
      letter-spacing: 0.05em;
      text-transform: uppercase;
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
      background: #fdfdfc;
      font-size: 0.92rem;
      font-weight: 600;
      color: var(--text);
      border-bottom: 2px solid var(--border);
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
      font-weight: 500;
      font-size: 0.92rem;
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
      font-weight: 600;
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
      font-weight: 400;
      font-size: 0.92rem;
    }}
    .na {{
      color: rgba(71, 85, 105, 0.3);
      font-weight: 400;
    }}
    .flag {{
      cursor: help;
      margin-left: 0.25rem;
    }}
    /* Chart */
    .chart-wrap {{
      position: relative;
      padding: 1.5rem;
      height: 320px;
      width: 100%;
    }}
    /* Sanity section */
    .sanity-wrap {{
      padding: 0; /* Let the table fill the card boundaries */
    }}
    .all-good {{
      color: #059669;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 500;
      padding: 1.5rem 2rem;
    }}
    .flagged-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }}
    .flagged-table th, .flagged-table td {{
      padding: 0.9rem 1.5rem;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    .flagged-table th {{
      background: #fdfdfc;
      font-weight: 600;
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 2px solid var(--border);
    }}
    .flagged-table tr:last-child td {{
      border-bottom: none;
    }}
    .flagged-table tr:hover td {{
      background-color: var(--surface-hover);
    }}
    .flagged-price, .flagged-deviation {{
      color: #dc2626;
      font-weight: 500; /* normal, not bold */
    }}
    .price.outlier {{
      color: #dc2626;
      font-weight: 500; /* normal, not bold */
    }}
    .table-note {{
      font-size: 0.82rem;
      color: var(--muted);
      margin-top: 0.75rem;
      font-style: italic;
      line-height: 1.45;
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
  <header class="site-header">
    <div class="header-main">
      <div class="brand-zone">
        <div class="brand-logo">GPU</div>
        <div class="brand-details">
          <h1>Pricing Tracker</h1>
          <p class="subtitle-text">NVIDIA SXM On-Demand GPU Instances</p>
        </div>
      </div>
      <div class="header-meta">
        <div class="status-badge">
          <span class="status-dot"></span>
          <span class="status-text">Active Monitoring</span>
        </div>
        <div class="update-badge">
          Last Updated: {last_updated}
        </div>
      </div>
    </div>
    <div class="header-sub">
      NVIDIA H100 · H200 · B200 · B300 · SXM variants · On-demand pricing · USD/hr
    </div>
  </header>

  <div class="table-header-actions">
    <p class="section-title">Current Prices (USD / hr)</p>
    <div class="header-buttons">
      <button id="triggerScrapeBtn" onclick="triggerWorkflow()" class="btn-copy btn-action">Trigger Scrape</button>
      <button id="copyTableBtn" onclick="copyTableToClipboard()" class="btn-copy">Copy to Excel</button>
    </div>
  </div>
  <div class="card-wrap table-wrap">
    {table_html}
  </div>
  <p class="table-note">* Note: Averages (but not medians) exclude pricing anomalies that are more than 50% above or below the overall median. Outliers are highlighted in red.</p>

  <p class="section-title">Sanity Check — Flagged Prices</p>
  <div class="card-wrap sanity-wrap">
    {flagged_html}
  </div>

  <p class="section-title">Price Trends — Lowest Available per Chip</p>
  <div class="card-wrap chart-wrap">
    <canvas id="trendChart"></canvas>
  </div>

  <footer>
    Updated automatically every 7 days via GitHub Actions ·
    Powered by Playwright + Browserbase + Llama 3.3 70B (Groq) ·
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
      tsv += rowData.join("\\t") + "\\n";
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
        maintainAspectRatio: false,
        plugins: {{
          legend: {{
            labels: {{
              color: "#0f172a",
              font: {{ family: "'Inter', sans-serif", size: 12, weight: 500 }}
            }}
          }}
        }},
        scales: {{
          x: {{
            ticks: {{ color: "#475569", font: {{ family: "'Inter', sans-serif" }} }},
            grid: {{ color: "rgba(0, 0, 0, 0.05)" }}
          }},
          y: {{
            ticks: {{
              color: "#475569",
              font: {{ family: "'Inter', sans-serif" }},
              callback: v => "$" + v.toFixed(2)
            }},
            grid: {{ color: "rgba(0, 0, 0, 0.05)" }},
            title: {{
              display: true,
              text: "USD / hr",
              color: "#475569",
              font: {{ family: "'Inter', sans-serif", weight: 600 }}
            }}
          }}
        }}
      }}
    }});
  }} else {{
    document.getElementById("trendChart").parentElement.innerHTML =
      "<p style='color:#64748b;text-align:center;padding:2rem'>Trend chart will appear after the second run.</p>";
  }}

  function triggerWorkflow() {{
    const btn = document.getElementById("triggerScrapeBtn");
    const originalText = btn.innerText;
    btn.innerText = "Triggering...";
    btn.disabled = true;

    const apiUrl = window.location.hostname.includes("vercel.app")
      ? "/api/index"
      : "https://pricing-tracker-inxq.vercel.app/api/index";

    fetch(apiUrl, {{
      method: "POST"
    }})
    .then(response => {{
      if (response.ok) {{
        btn.innerText = "✓ Triggered!";
        btn.classList.add("btn-success");
        setTimeout(() => {{
          btn.innerText = originalText;
          btn.classList.remove("btn-success");
          btn.disabled = false;
        }}, 3000);
      }} else {{
        return response.json().then(data => {{
          throw new Error(data.error || "HTTP " + response.status);
        }}).catch(() => {{
          throw new Error("HTTP " + response.status);
        }});
      }}
    }})
    .catch(err => {{
      console.error(err);
      alert("Failed to trigger scrape: " + err.message + "\\n\\nMake sure GITHUB_PAT is set in Vercel's Environment Variables.");
      btn.innerText = originalText;
      btn.disabled = false;
    }});
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
