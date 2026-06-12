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
groq_key = os.environ.get("GROQ_API_KEY", "").strip()
if not groq_key:
    raise ValueError("GROQ_API_KEY is not set or is empty. Please set it in your environment or repository secrets.")
groq_client = AsyncGroq(api_key=groq_key)

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
            CRITICAL: You must ONLY use prices from the SERVERLESS section of this page.
            Do NOT use prices from the 'GPU Cloud', 'Pods', 'Secure Cloud', or 'Community Cloud' sections.

            In the Serverless section, find the per-hour compute price for each GPU:
            - H100 SXM (also listed as H100 SXM, H100 80GB SXM) → correct price is approximately $4.18/hr
            - H200 SXM → extract from Serverless section only
            - B200 SXM → extract from Serverless section only
            - B300 SXM → extract from Serverless section only

            The Serverless section shows a price per GPU-Hour ($/hr). Extract that specific value.

            IMPORTANT:
            - ONLY use Serverless section prices. Ignore all other sections.
            - SXM variants only — ignore PCIe.
            - Prices in USD per hour.
            - If not listed in Serverless section, return null.
        """,
    },
    {
        "id": "together",
        "name": "Together AI",
        "url": "https://www.together.ai/pricing#gpu-clusters",
        "task": """
            Scroll down to the GPU Clusters pricing section.
            Extract the hourly on-demand price for:
            - H100 SXM (listed as 'NVIDIA HGX H100')
            - H200 SXM (listed as 'NVIDIA HGX H200')
            - B200 SXM (listed as 'NVIDIA HGX B200')
            - B300 SXM
            IMPORTANT:
            - HGX/SXM variants only. HGX denotes the SXM variant here. Ignore PCIe.
            - On-demand / pay-as-you-go hourly only (listed under 'On-demand'). Ignore reserved or committed.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "nebius",
        "name": "Nebius",
        "url": "https://nebius.com/prices",
        "task": """
            Find the NVIDIA GPU Instances pricing table.
            Extract the hourly on-demand price (under the 'On-demand, GPU-hour' column) for:
            - H100 SXM (listed as 'NVIDIA HGX H100')
            - H200 SXM (listed as 'NVIDIA HGX H200')
            - B200 SXM (listed as 'NVIDIA HGX B200')
            - B300 SXM (listed as 'NVIDIA HGX B300')
            IMPORTANT:
            - HGX/SXM variants only. HGX denotes the SXM variant here. Ignore PCIe.
            - On-demand hourly pricing only. Ignore preemptible or committed rates.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "lambda",
        "name": "Lambda Labs",
        "url": "https://lambda.ai/pricing",
        "task": """
            Find the 'Instances pricing' table.
            Extract the hourly on-demand price (under the 'PRICE/GPU/HR' column) for:
            - H100 SXM (listed as 'NVIDIA H100 SXM')
            - H200 SXM
            - B200 SXM (listed as 'NVIDIA B200 SXM6')
            - B300 SXM
            IMPORTANT:
            - SXM variants only (e.g. H100 SXM, B200 SXM6). Ignore PCIe.
            - On-demand / hourly only. If there are reserved or cluster-duration columns, ignore them.
            - Prices in USD per hour.
            - If not listed, return null.
        """,
    },
    {
        "id": "spheron",
        "name": "Spheron",
        "url": "https://www.spheron.network/gpu-rental/h100/",
        "extra_urls": [
            "https://www.spheron.network/gpu-rental/h200/",
            "https://www.spheron.network/gpu-rental/b200/",
            "https://www.spheron.network/gpu-rental/b300/",
        ],
        "task": """
            Each section of the text below comes from a dedicated GPU page on Spheron.
            Each page shows a price in the format "from $X.XX/hr" or "starts at $X.XX/hr" or "$X.XX/hr per GPU per hour" near the top of the page.
            Extract the DEDICATED (on-demand, non-spot) hourly price for each GPU:
            - H100 SXM — look for it in the H100 page section (starts at $2.01/hr)
            - H200 SXM — look for it in the H200 page section (starts at $3.31/hr)
            - B200 SXM — look for it in the B200 page section (starts at $2.71/hr)
            - B300 SXM — look for it in the B300 page section (starts at $3.29/hr)

            IMPORTANT:
            - Use ONLY the dedicated on-demand (non-spot) price. Ignore spot prices.
            - SXM/HGX variants only.
            - Prices in USD per hour.
            - If not found, return null.
        """,
    },
    {
        "id": "e2e",
        "name": "E2E Networks",
        "url": "https://www.e2enetworks.com/pricing",
        "task": """
            Find the NVIDIA GPU pricing table.
            IMPORTANT CURRENCY NOTE: All prices on this site are in Indian Rupees (INR), denoted by '₹'.
            You must convert every price to USD by dividing by 96. For example: ₹624.00/hr → $6.50/hr.
            Extract the Hourly/On-Demand price (converted to USD by dividing by 96) for:
            - H100 SXM (listed as 'NVIDIA H100')
            - H200 SXM (listed as 'NVIDIA H200')
            - B200 SXM (listed as 'NVIDIA B200')
            - B300 SXM
            IMPORTANT:
            - Treat the standard 'NVIDIA H100', 'NVIDIA H200', 'NVIDIA B200' rows as the target SXM variants.
            - On-demand / pay-as-you-go hourly only (under 'Hourly/On-Demand' column). Ignore monthly/annually.
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
            browserbase_key = os.environ.get("BROWSERBASE_API_KEY")
            use_local = True
            if browserbase_key:
                try:
                    print("Connecting to Browserbase cloud browser...")
                    from browserbase import Browserbase
                    bb = Browserbase(api_key=browserbase_key)
                    session = await asyncio.to_thread(bb.sessions.create)
                    print(f"Browserbase Session Created: {session.id}")
                    browser = await p.chromium.connect_over_cdp(session.connect_url)
                    # Browserbase remote sessions have a context and page pre-opened
                    context = browser.contexts[0].pages[0]
                    use_local = False
                except Exception as bb_err:
                    err_str = str(bb_err)
                    if "402" in err_str or "Payment Required" in err_str or "limit reached" in err_str:
                        print(f"  Browserbase quota exceeded (402). Falling back to local Chromium...")
                    else:
                        print(f"  Browserbase error: {bb_err}. Falling back to local Chromium...")
                    use_local = True
            else:
                print("BROWSERBASE_API_KEY missing, launching local Chromium...")

            if use_local:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_page()

            # Navigate to the page
            print(f"Navigating to {site['url']}...")
            try:
                # Use a reasonable timeout (e.g. 15 seconds)
                await context.goto(site["url"], wait_until="domcontentloaded", timeout=15000)
            except Exception as navigation_err:
                print(f"  Navigation warning: {navigation_err} (proceeding with current content)")

            # Wait a short moment for dynamic components to finish loading
            await context.wait_for_timeout(3000)

            # Remove cookie consent banners that might block clicking/viewing, making sure not to remove root elements
            try:
                await context.evaluate("""
                    document.querySelectorAll('[id*="cookie"], [class*="cookie"], [id*="consent"], [class*="consent"]').forEach(el => {
                        if (el.tagName !== 'BODY' && el.tagName !== 'HTML') {
                            el.remove();
                        }
                    });
                """)
            except Exception as eval_err:
                print(f"  Cookie removal warning: {eval_err}")

            # Extract page text
            text_content = await context.evaluate("document.body.innerText")
            if "extra_urls" in site:
                text_content = text_content[:4000]

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

            # Handle extra_urls: navigate to additional pages and accumulate their text
            if "extra_urls" in site:
                for extra_url in site["extra_urls"]:
                    print(f"  Navigating to extra URL: {extra_url}...")
                    try:
                        await context.goto(extra_url, wait_until="domcontentloaded", timeout=15000)
                    except Exception as nav_err:
                        print(f"  Extra URL navigation warning: {nav_err} (proceeding)")
                    await context.wait_for_timeout(2000)
                    extra_text = await context.evaluate("document.body.innerText")
                    text_content += f"\n\n--- EXTRA PAGE ({extra_url}) ---\n\n" + extra_text[:4000]

            await browser.close()

            # Clean text to save tokens
            cleaned_text = clean_extracted_text(text_content)
            
            # For RunPod, isolate the serverless section specifically to prevent model confusion
            if site["id"] == "runpod":
                match_start = re.search(r"Serverless\n(?:\[\.\.\.\]\n)?Cost effective", cleaned_text, re.IGNORECASE)
                if match_start:
                    start_idx = match_start.start()
                    end_idx = cleaned_text.find("Clusters", start_idx)
                    if end_idx != -1:
                        cleaned_text = cleaned_text[start_idx:end_idx]

            # Hard-cap to 3000 chars to stay well within Groq TPD limits
            MAX_GROQ_CHARS = 3000
            if len(cleaned_text) > MAX_GROQ_CHARS:
                cleaned_text = cleaned_text[:MAX_GROQ_CHARS]
                print(f"  Text capped at {MAX_GROQ_CHARS} chars to save tokens.")

            print(f"Extracted {len(text_content)} chars. Cleaned to {len(cleaned_text)} chars. Parsing with Groq...")

            # Call Groq Async client — retry up to 3 times on 429 rate-limit
            groq_response = None
            for _attempt in range(3):
                try:
                    groq_response = await groq_client.chat.completions.create(
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
                    break  # success — exit retry loop
                except Exception as groq_err:
                    err_str = str(groq_err)
                    if "429" in err_str or "rate_limit" in err_str.lower():
                        # Extract wait time from error message if possible
                        wait_match = re.search(r'try again in (\d+)m', err_str)
                        wait_secs = int(wait_match.group(1)) * 60 + 30 if wait_match else 120
                        # Cap wait to 3 minutes so workflow doesn't time out
                        wait_secs = min(wait_secs, 180)
                        print(f"  Groq 429 rate limit hit (attempt {_attempt+1}/3). Waiting {wait_secs}s...")
                        await asyncio.sleep(wait_secs)
                    else:
                        raise  # re-raise non-rate-limit errors immediately

            if groq_response is None:
                raise Exception("Groq rate limit persisted after 3 retries — skipping site.")

            response = groq_response
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

    # Build structured result
    chips_data = {}
    for chip in TARGET_CHIPS:
        price = prices.get(chip)
        chips_data[chip] = {
            "price_usd_per_hour": price,
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
    
    # Check if we successfully extracted at least some pricing data
    total_prices = 0
    for r in results:
        for chip in TARGET_CHIPS:
            if r["chips"][chip]["price_usd_per_hour"] is not None:
                total_prices += 1
                
    if total_prices == 0:
        print("\nERROR: Scraper failed to extract any prices. Exiting to prevent overwriting dashboard data with nulls.")
        import sys
        sys.exit(1)

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
            cell = f"${val:.2f}" if val else "   N/A"
            row += f" {cell:>8}"
        print(row)


if __name__ == "__main__":
    asyncio.run(main())
