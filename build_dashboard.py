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
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

    def fmt_label(run_at_str):
        """Format ISO timestamp as '12 Jun 11:10 IST'."""
        dt = datetime.fromisoformat(run_at_str.replace("Z", "+00:00"))
        ist_dt = dt.astimezone(IST)
        day = str(ist_dt.day)          # no leading zero, cross-platform
        mon = ist_dt.strftime("%b")    # e.g. Jun
        hhmm = ist_dt.strftime("%H:%M")
        return f"{day} {mon} {hhmm} IST"  # e.g. 12 Jun 11:10 IST

    # Collect all run timestamps as short IST labels
    labels = [fmt_label(h["run_at"]) for h in history]

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
                        diff_pct_val = abs(diff_pct)
                        sign_char = "+" if diff_pct > 0 else "-"
                        diff_str = f'<span class="deviation-sign">{sign_char}</span>{diff_pct_val:.1f}%'
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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
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
      padding: 0 0 2rem 0;
      border-bottom: 1px solid var(--border);
      margin-bottom: 2.5rem;
    }}
    .header-main {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 1.5rem;
    }}
    .brand-details h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 2.25rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.03em;
      line-height: 1.15;
      margin: 0;
    }}
    .subtitle-text {{
      color: var(--muted);
      font-size: 0.95rem;
      margin-top: 0.4rem;
    }}
    .header-meta {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #166534;
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
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
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 500;
      color: var(--muted);
    }}
    .header-pills-row {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-top: 1.25rem;
    }}
    .pill {{
      font-size: 0.72rem;
      font-weight: 500;
      color: var(--muted);
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .pill.chip-pill {{
      font-weight: 600;
    }}
    .pill.chip-pill.h100 {{
      border-color: #bfdbfe;
      color: #1e40af;
      background: #eff6ff;
    }}
    .pill.chip-pill.h200 {{
      border-color: #ffedd5;
      color: #9a3412;
      background: #fff7ed;
    }}
    .pill.chip-pill.b200 {{
      border-color: #d1fae5;
      color: #065f46;
      background: #ecfdf5;
    }}
    .pill.chip-pill.b300 {{
      border-color: #ffe4e6;
      color: #9f1239;
      background: #fff1f2;
    }}
    .pill-divider {{
      color: var(--border);
      margin: 0 0.25rem;
      font-weight: 300;
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
      text-align: center;
      border-bottom: 1px solid var(--border);
    }}
    th:first-child, td:first-child {{
      text-align: left;
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
      text-align: left; /* Keep group headers left-aligned */
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
    .progress-wrap {{
      margin-bottom: 2rem;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
    }}
    .progress-content {{
      display: flex;
      align-items: center;
      gap: 1.5rem;
      padding: 1.5rem 2rem;
    }}
    .progress-circle-wrap {{
      position: relative;
      width: 80px;
      height: 80px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .progress-ring {{
      transform: rotate(-90deg);
    }}
    .progress-ring__circle-bg {{
      stroke: var(--bg);
    }}
    .progress-ring__circle {{
      stroke-dasharray: 213.63;
      stroke-dashoffset: 213.63;
      transition: stroke-dashoffset 0.35s;
      transform-origin: 50% 50%;
      stroke-linecap: round;
    }}
    .progress-text {{
      position: absolute;
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
    }}
    .progress-info h3 {{
      font-size: 1.05rem;
      font-weight: 600;
      margin: 0 0 0.25rem 0;
      color: var(--text);
    }}
    .progress-info p {{
      font-size: 0.88rem;
      color: var(--muted);
      margin: 0;
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
      text-align: center;
    }}
    .flagged-table th:first-child, .flagged-table td:first-child {{
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
      font-weight: 600;
    }}
    .deviation-sign {{
      font-size: 1.35em;
      font-weight: 800;
      margin-right: 0.05em;
      vertical-align: middle;
      display: inline-block;
      line-height: 0.9;
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
      <div class="brand-details">
        <h1>GPU Pricing Tracker</h1>
        <p class="subtitle-text">Real-time cost tracking for NVIDIA SXM On-Demand GPU Instances</p>
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
    <div class="header-pills-row">
      <span class="pill">SXM Variants</span>
      <span class="pill">On-Demand Pricing</span>
      <span class="pill">USD / Hour</span>
      <span class="pill-divider">|</span>
      <span class="pill chip-pill h100">H100</span>
      <span class="pill chip-pill h200">H200</span>
      <span class="pill chip-pill b200">B200</span>
      <span class="pill chip-pill b300">B300</span>
    </div>
  </header>

  <div class="table-header-actions">
    <p class="section-title">Current Prices (USD / hr)</p>
    <div class="header-buttons">
      <button id="triggerScrapeBtn" onclick="triggerWorkflow()" class="btn-copy btn-action">Trigger Scrape</button>
      <button id="copyTableBtn" onclick="copyTableToClipboard()" class="btn-copy">Copy to Excel</button>
    </div>
  </div>
  <!-- Progress Panel -->
  <div id="progressContainer" class="card-wrap progress-wrap" style="display: none;">
    <div class="progress-content">
      <div class="progress-circle-wrap">
        <svg class="progress-ring" width="80" height="80">
          <circle class="progress-ring__circle-bg" stroke="#f1f5f9" stroke-width="6" fill="transparent" r="34" cx="40" cy="40"/>
          <circle class="progress-ring__circle" stroke="#2563eb" stroke-width="6" fill="transparent" r="34" cx="40" cy="40"/>
        </svg>
        <div id="progressPercent" class="progress-text">0%</div>
      </div>
      <div class="progress-info">
        <h3 id="progressTitle">Scraping in progress...</h3>
        <p id="progressStatus">Initializing runner...</p>
      </div>
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
    Powered by Playwright + Gemini 2.0 Flash
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
            ticks: {{
              color: "#475569",
              font: {{ family: "'Inter', sans-serif", size: 10 }},
              maxRotation: 45,
              minRotation: 30,
            }},
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

  let progressInterval = null;
  let fakeProgressInterval = null;
  let currentFakeProgress = 40;
  let clickTime = null;

  function checkProgress() {{
    const apiUrl = window.location.hostname.includes("vercel.app")
      ? "/api/index"
      : "https://pricing-tracker-inxq.vercel.app/api/index";

    fetch(apiUrl)
      .then(r => r.json())
      .then(data => {{
        if (data.status === "active") {{
          showProgress(data);
          if (!progressInterval) {{
            progressInterval = setInterval(checkProgress, 3000);
          }}
        }} else {{
          hideProgress(data);
        }}
      }})
      .catch(err => console.error("Error checking progress:", err));
  }}

  function initProgressTracker() {{
    checkProgress();
    // Default slow poll fallback
    setInterval(() => {{
      if (!progressInterval) {{
        checkProgress();
      }}
    }}, 15000);
  }}

  function showProgress(runData) {{
    document.getElementById("progressContainer").style.display = "block";
    const btn = document.getElementById("triggerScrapeBtn");
    btn.disabled = true;
    btn.innerText = "Scrape In Progress...";

    const job = runData.jobs && runData.jobs[0];
    if (!job) return;

    const steps = job.steps || [];
    let completedCount = 0;
    let activeStep = null;

    for (let step of steps) {{
      if (step.status === "completed") {{
        completedCount++;
      }} else if (step.status === "in_progress") {{
        activeStep = step;
        break;
      }}
    }}

    let progress = 5;
    let statusText = "Initializing runner...";

    if (activeStep) {{
      statusText = `Active step: ${{activeStep.name}}...`;
      if (activeStep.name.includes("Checkout")) {{
        progress = 15;
      }} else if (activeStep.name.includes("Python")) {{
        progress = 20;
      }} else if (activeStep.name.includes("Install")) {{
        progress = 30;
      }} else if (activeStep.name.includes("scraper")) {{
        progress = 40;
        if (!fakeProgressInterval) {{
          currentFakeProgress = 40;
          fakeProgressInterval = setInterval(() => {{
            if (currentFakeProgress < 75) {{
              currentFakeProgress += 0.5;
              setProgress(currentFakeProgress);
              const providerEstimate = getEstimatedProvider(currentFakeProgress);
              document.getElementById("progressStatus").innerText = `Scraping providers (${{providerEstimate}})...`;
            }}
          }}, 1000);
        }}
      }} else if (activeStep.name.includes("dashboard")) {{
        progress = 85;
        if (fakeProgressInterval) {{ clearInterval(fakeProgressInterval); fakeProgressInterval = null; }}
      }} else if (activeStep.name.includes("Commit")) {{
        progress = 90;
        if (fakeProgressInterval) {{ clearInterval(fakeProgressInterval); fakeProgressInterval = null; }}
      }}
    }} else {{
      if (completedCount > 0) {{
        progress = Math.min(95, completedCount * 12);
      }}
    }}

    if (!fakeProgressInterval) {{
      setProgress(progress);
      document.getElementById("progressStatus").innerText = statusText;
    }}
  }}

  function hideProgress(runData) {{
    if (progressInterval) {{
      clearInterval(progressInterval);
      progressInterval = null;
    }}
    if (fakeProgressInterval) {{
      clearInterval(fakeProgressInterval);
      fakeProgressInterval = null;
    }}
    document.getElementById("progressContainer").style.display = "none";
    const btn = document.getElementById("triggerScrapeBtn");
    btn.disabled = false;
    btn.innerText = "Trigger Scrape";

    const lastRun = runData.last_run;
    if (lastRun && lastRun.status === "completed" && clickTime && (new Date(lastRun.updated_at) > clickTime)) {{
      if (lastRun.conclusion === "success") {{
        clickTime = null;
        document.getElementById("progressContainer").style.display = "block";
        let secondsLeft = 15;
        const countdownFn = () => {{
          document.getElementById("progressStatus").innerText = `✓ Scrape complete! Reloading in ${{secondsLeft}}s for new prices...`;
          if (secondsLeft > 0) {{
            secondsLeft--;
            setTimeout(countdownFn, 1000);
          }} else {{
            window.location.reload();
          }}
        }};
        setProgress(100);
        countdownFn();
      }} else {{
        clickTime = null;
        alert("❌ Scrape failed! Please check GitHub Actions logs or scraper_log.txt for details.");
      }}
    }}
  }}

  function setProgress(percent) {{
    const circle = document.querySelector('.progress-ring__circle');
    if (!circle) return;
    const radius = circle.r.baseVal.value;
    const circumference = radius * 2 * Math.PI;
    circle.style.strokeDasharray = `${{circumference}} ${{circumference}}`;
    const offset = circumference - (percent / 100) * circumference;
    circle.style.strokeDashoffset = offset;
    document.getElementById("progressPercent").innerText = `${{Math.round(percent)}}%`;
  }}

  function getEstimatedProvider(pct) {{
    if (pct < 45) return "Neysa / Verda";
    if (pct < 50) return "RunPod";
    if (pct < 55) return "Together AI";
    if (pct < 60) return "Nebius";
    if (pct < 65) return "Lambda Labs";
    if (pct < 70) return "Spheron";
    return "E2E Networks";
  }}

  function triggerWorkflow() {{
    const btn = document.getElementById("triggerScrapeBtn");
    const originalText = btn.innerText;
    btn.innerText = "Triggering...";
    btn.disabled = true;

    clickTime = new Date();

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
          btn.classList.remove("btn-success");
          checkProgress();
        }}, 1000);
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
      clickTime = null;
    }});
  }}

  document.addEventListener("DOMContentLoaded", initProgressTracker);
</script>

</body>
</html>
"""


def main():
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    latest, history = load_data()
    html = generate_html(latest, history)

    # Write to docs/index.html for GitHub Pages
    out_docs = docs_dir / "index.html"
    out_docs.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {out_docs}")

    # Write to root index.html for Vercel
    out_root = Path("index.html")
    out_root.write_text(html, encoding="utf-8")
    print(f"Dashboard written to {out_root}")


if __name__ == "__main__":
    main()
