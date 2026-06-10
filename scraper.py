"""
GPU Pricing Tracker — Playwright + Groq (Llama 3.3 70B)
Targets: H100 SXM, H200 SXM, B200 SXM, B300 SXM
Runs every 7 days via GitHub Actions
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from groq import AsyncGroq

load_dotenv()

# ── Groq Client setup ────────────────────────────────────────────────────────
groq_client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

# ── Target chips ──────────────────────────────────────────────────────────────
TARGET_CHIPS = ["H100", "H200", "B200", "B300"]

# Alias terms different sites may use — agent is told to match these
CHIP_ALIASES = {
    "H100": ["H100 SXM", "H100 SXM4", "H100 SXM5", "H100 80GB SXM", "H100-SXM"],
    "H200": ["H200 SXM", "H200 SXM5", "H200 141GB", "H200 HBM3e"],
    "B200": ["B200 SXM", "B200 SXM5"],
    "B300": ["B300 SXM", "B300"],
}

# ── Site task definitions ─────────────────────────────────────────────────────
SITES = [
    {
        "id": "neysa",
        "name": "Neysa",
        "url": "https://neysa.ai/pricing/",
        "task": """
            Find the GPU pricing table or section.
            Extract the hourly on-demand price (pay-as-you-go, not reserved or committed) for these NVIDIA GPU chips:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM (also listed as H200 SXM5, H200 141GB)
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - Only extract SXM variants. Ignore PCIe variants entirely.
            - Only extract on-demand / pay-as-you-go / hourly pricing. Ignore reserved, committed, or contract pricing.
            - If a chip is not listed, mark it as null.
            - All prices must be in USD per hour.
        """,
    },
    {
        "id": "verda",
        "name": "Verda",
        "url": "https://verda.com/products#H100",
        "task": """
            Extract the hourly on-demand price for the SXM variant specifically:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM (also listed as H200 SXM5)
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - Only extract SXM variants. Ignore PCIe.
            - Only on-demand pricing. Ignore reserved or committed.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "runpod",
        "name": "RunPod",
        "url": "https://www.runpod.io/pricing",
        "task": """
            Find the GPU pricing section. RunPod shows two categories: Secure Cloud and Community Cloud.
            Extract the hourly price from Secure Cloud only (ignore Community Cloud).
            Find the on-demand hourly price for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / pay-as-you-go only.
            - Prices in USD per hour.
            - If not listed, return null.
            - You have to extract the prices under the "Serverless" category. 
            - Within the serverless, you have to extract the hourly pricing. 
        """,
    },
    {
        "id": "together",
        "name": "Together AI",
        "url": "https://www.together.ai/pricing#gpu-clusters",
        "task": """
            Scroll down to the GPU Clusters pricing section.
            Extract the hourly on-demand price for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / pay-as-you-go hourly only. Ignore reserved or committed.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "nebius",
        "name": "Nebius",
        "url": "https://nebius.com/prices",
        "task": """
            Find the GPU or compute pricing section.
            Extract the hourly on-demand price for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / pay-as-you-go hourly only. Ignore reserved or committed.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "lambda",
        "name": "Lambda Labs",
        "url": "https://lambda.ai/pricing",
        "task": """
            Find the GPU on-demand pricing table.
            Extract the hourly on-demand price for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / hourly only. If there are reserved or 1-year pricing columns, ignore them.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "spheron",
        "name": "Spheron",
        "url": "https://www.spheron.network/gpu-rental/",
        "task": """
            Find the GPU rental pricing on this page.
            Extract the hourly on-demand price for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / spot / pay-as-you-go hourly only.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "e2e",
        "name": "E2E Networks",
        "url": "https://www.e2enetworks.com/pricing",
        "task": """
            Find the GPU or compute pricing section.
            IMPORTANT CURRENCY NOTE: All prices on this site are in Indian Rupees (INR).
            You must convert every price to USD by dividing by 96. For example: ₹2,000/hr → $20.83/hr.
            Extract the hourly on-demand price (converted to USD) for:
            - H100 SXM (also listed as H100 SXM4, H100 SXM5, H100 80GB SXM)
            - H200 SXM
            - B200 SXM
            - B300 SXM
            IMPORTANT:
            - SXM variants only — ignore PCIe.
            - On-demand / pay-as-you-go hourly only.
            - Convert INR to USD by dividing by 96.
            - Return prices in USD per hour.
            - If not listed, return null.
        """,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_json_from_result(text: str) -> dict | None:
    """Pull the first JSON object out of whatever the agent returned."""
    match = re.search(r'\{.*?\}', str(text), re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def sanity_check(chip: str, price: float | None) -> str:
    """Return 'ok', 'flagged', or 'null'."""
    if price is None:
        return "null"
    lo, hi = SANITY_RANGES.get(chip, (0, 9999))
    return "ok" if lo <= price <= hi else "flagged"


def clean_extracted_text(text: str) -> str:
    """Filter page text to only keep lines that are relevant to GPU pricing to save tokens."""
    lines = text.split("\n")
    relevant_lines = []

    # Keywords to identify relevant lines
    keywords = [
        "h100", "h200", "b200", "b300", "a100", "rtx", "gpu", "sxm", "pcie", "nvidia", 
        "price", "hour", "ondemand", "/hr", "pricing", "cost", "$", "₹", "rupee", "rub",
        "demand", "reserved", "spot", "rental", "compute"
    ]

    # Match indices of lines that contain any keyword (case-insensitive)
    matching_indices = set()
    for i, line in enumerate(lines):
        clean_line = line.strip().lower()
        if any(kw in clean_line for kw in keywords):
            matching_indices.add(i)

    # Include matching lines + their immediate neighbors (1 line before/after) to keep context (e.g. headers)
    indices_to_keep = set()
    for idx in matching_indices:
        indices_to_keep.add(max(0, idx - 1))
        indices_to_keep.add(idx)
        indices_to_keep.add(min(len(lines) - 1, idx + 1))

    # Rebuild cleaned text
    last_idx = -2
    for idx in sorted(indices_to_keep):
        line = lines[idx].strip()
        if not line:
            continue
        # Add visual separator if there's a gap between kept lines
        if idx > last_idx + 1 and relevant_lines:
            relevant_lines.append("[...]")
        relevant_lines.append(line)
        last_idx = idx

    return "\n".join(relevant_lines)


# ── Core scraping logic ───────────────────────────────────────────────────────

async def scrape_site(site: dict) -> dict:
    """Run Playwright to load the page, extract text, and parse pricing with Groq."""
    print(f"\n{'='*60}")
    print(f"Scraping: {site['name']} — {site['url']}")
    print(f"{'='*60}")

    prices = {chip: None for chip in TARGET_CHIPS}

    try:
        async with async_playwright() as p:
            # Force Browserbase usage (no local Chromium fallback)
            browserbase_key = os.environ.get("BROWSERBASE_API_KEY")
            if not browserbase_key:
                raise ValueError("Error: BROWSERBASE_API_KEY environment variable is missing. You must configure this key to run the scraper.")
            
            print("Connecting to Browserbase cloud browser...")
            from browserbase import Browserbase
            bb = Browserbase(api_key=browserbase_key)
            session = await asyncio.to_thread(bb.sessions.create)
            print(f"Browserbase Session Created: {session.id}")
            browser = await p.chromium.connect_over_cdp(session.connect_url)
            # Browserbase remote sessions have a context and page pre-opened
            context = browser.contexts[0].pages[0]

            # Navigate to the page
            print(f"Navigating to {site['url']}...")
            try:
                # Use a reasonable timeout (e.g. 15 seconds)
                await context.goto(site["url"], wait_until="networkidle", timeout=15000)
            except Exception as navigation_err:
                print(f"  Navigation warning: {navigation_err} (proceeding with current content)")

            # Wait a short moment for dynamic components to finish loading
            await context.wait_for_timeout(3000)

            # Extract page text
            text_content = await context.evaluate("document.body.innerText")

            # Handle dynamic tab clicking if selectors are defined
            if "selectors_to_click" in site:
                for selector in site["selectors_to_click"]:
                    print(f"  Clicking tab selector: {selector}...")
                    try:
                        await context.click(selector, timeout=5000)
                        await context.wait_for_timeout(1500)
                        tab_text = await context.evaluate("document.body.innerText")
                        # Accumulate all tab content separated by markers
                        text_content += f"\n\n--- TAB CONTENT ({selector}) ---\n\n" + tab_text
                    except Exception as click_err:
                        print(f"  Click warning for {selector}: {click_err}")

            await browser.close()

            # Clean text to save tokens
            cleaned_text = clean_extracted_text(text_content)
            print(f"Extracted {len(text_content)} chars. Cleaned to {len(cleaned_text)} chars. Parsing with Groq...")

            # Call Groq Async client
            response = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a structured data extraction assistant. Your task is to extract NVIDIA GPU pricing information "
                            "from the webpage text provided. You must output a JSON object containing the on-demand hourly price (in USD) "
                            "for the following chips:\n"
                            "- H100 (SXM variants only)\n"
                            "- H200 (SXM variants only)\n"
                            "- B200 (SXM variants only)\n"
                            "- B300 (SXM variants only)\n\n"
                            "You must follow the site-specific extraction task instructions exactly. "
                            "Return ONLY a JSON object with the exact keys: \"H100\", \"H200\", \"B200\", \"B300\". "
                            "Do not include any extra text, comments, or markdown code blocks. Just output the raw JSON object.\n"
                            "Use null for any chips that are not listed on the page."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Site-specific task details:\n{site['task']}\n\nWebpage text:\n{cleaned_text}"
                    }
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            raw_output = response.choices[0].message.content
            print(f"Raw output: {raw_output}")

            parsed_prices = extract_json_from_result(raw_output)
            if parsed_prices:
                # Merge into our price dictionary and validate type
                for chip in TARGET_CHIPS:
                    if chip in parsed_prices:
                        val = parsed_prices[chip]
                        if isinstance(val, (int, float)):
                            prices[chip] = float(val)
                        elif isinstance(val, str):
                            # Try parsing string to float
                            try:
                                clean_val = re.sub(r'[^\d\.]', '', val)
                                prices[chip] = float(clean_val)
                            except ValueError:
                                prices[chip] = None
            else:
                print(f"  WARNING: Could not parse JSON from {site['name']} output")

    except Exception as e:
        print(f"  ERROR scraping {site['name']}: {e}")

    # Build structured result with sanity flags
    chips_data = {}
    for chip in TARGET_CHIPS:
        price = prices.get(chip)
        chips_data[chip] = {
            "price_usd_per_hour": price,
            "status": sanity_check(chip, price),
        }

    return {
        "site_id": site["id"],
        "site_name": site["name"],
        "url": site["url"],
        "chips": chips_data,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_all_sites() -> list[dict]:
    """Scrape all sites sequentially (avoids rate limits)."""
    results = []
    for site in SITES:
        result = await scrape_site(site)
        results.append(result)
        # Brief pause between sites to be polite
        await asyncio.sleep(3)
    return results


# ── Save results ──────────────────────────────────────────────────────────────

def save_results(results: list[dict]):
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # 1. Save timestamped snapshot
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_path = data_dir / f"snapshot_{ts}.json"
    with open(snapshot_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSnapshot saved: {snapshot_path}")

    # 2. Overwrite latest.json (always the most recent run)
    latest_path = data_dir / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Latest saved:  {latest_path}")

    # 3. Append to history.json (all runs, for trend charts)
    history_path = data_dir / "history.json"
    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = []

    history.append({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    })

    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"History saved: {history_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    print("GPU Pricing Tracker — Starting run")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Chips: {TARGET_CHIPS}")
    print(f"Sites: {len(SITES)}")

    results = await run_all_sites()
    save_results(results)

    # Print summary table to console
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Site':<16} {'H100':>8} {'H200':>8} {'B200':>8} {'B300':>8}")
    print("-"*60)
    for r in results:
        row = f"{r['site_name']:<16}"
        for chip in TARGET_CHIPS:
            val = r["chips"][chip]["price_usd_per_hour"]
            flag = " !" if r["chips"][chip]["status"] == "flagged" else ""
            cell = f"${val:.2f}{flag}" if val else "   N/A"
            row += f" {cell:>8}"
        print(row)


if __name__ == "__main__":
    asyncio.run(main())
