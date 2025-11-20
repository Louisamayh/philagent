#!/usr/bin/env python3
"""
Test Phase 2 using links from an existing CSV file
Useful if you already have a links CSV from Phase 1
"""

import asyncio
import csv
from pathlib import Path
from browser_use import ChatGoogle
from job_scraper import scrape_single_job


async def test_phase2_from_csv(csv_path: str, max_jobs: int = 5):
    """
    Test Phase 2 by reading links from a CSV file

    Args:
        csv_path: Path to the links CSV file (e.g., "output/abc123_links.csv")
        max_jobs: Maximum number of jobs to test (default: 5)
    """

    # Check if file exists
    if not Path(csv_path).exists():
        print(f"❌ Error: File not found: {csv_path}")
        print("\nAvailable CSV files in output/:")
        output_dir = Path("output")
        if output_dir.exists():
            for f in output_dir.glob("*_links.csv"):
                print(f"  - {f}")
        return

    # Read links from CSV
    print(f"📄 Reading links from: {csv_path}")
    links = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            links.append({
                "link_url": row.get("link_url", ""),
                "link_text": row.get("link_text", ""),
                "page_number": row.get("page_number", "1"),
            })

    if not links:
        print("❌ No links found in CSV file")
        return

    # Limit to max_jobs
    links = links[:max_jobs]

    print(f"✅ Found {len(links)} links to test\n")

    # Initialize LLM
    llm = ChatGoogle(model="gemini-flash-latest")

    # Get search info from first row
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        first_row = next(reader)
        search_info = {
            "job_title": first_row.get("search_job_title", ""),
            "location": first_row.get("search_location", ""),
            "miles": first_row.get("search_radius_miles", "30")
        }

    print("=" * 60)
    print("🧪 Testing Phase 2: Job Scraping from CSV")
    print("=" * 60)
    print(f"Search: {search_info['job_title']} in {search_info['location']}")
    print(f"Testing {len(links)} jobs\n")

    results = []

    for idx, link in enumerate(links, 1):
        job_url = link['link_url']
        if not job_url:
            continue

        print(f"\n[{idx}/{len(links)}] Scraping: {job_url}")

        try:
            result = await scrape_single_job(
                llm=llm,
                job_url=job_url,
                search_info=search_info,
                max_steps=50
            )
            results.append(result)
            print(f"✅ {result.get('scraped_job_title', 'N/A')}")
            print(f"   Recruiter: {result.get('recruiter_name', 'N/A')}")
            print(f"   Location: {result.get('job_location_text', 'N/A')}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue

    print("\n" + "=" * 60)
    print(f"✅ Successfully scraped {len(results)}/{len(links)} jobs")
    print("=" * 60)

    # Save results to test output
    if results:
        output_path = "output/phase2_test_results.csv"
        import uuid
        from datetime import datetime

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "job_id", "source_url", "search_job_title", "search_location",
            "search_radius_miles", "scraped_job_title", "recruiter_name",
            "job_location_text", "salary_benefits", "description_snippet",
            "responsibilities_snippet"
        ]

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    print("\n🚀 Phase 2 Test Script (from CSV)\n")

    # Check for existing CSV files
    output_dir = Path("output")
    csv_files = []

    if output_dir.exists():
        csv_files = list(output_dir.glob("*_links.csv"))

    if csv_files:
        print("Available links CSV files:")
        for idx, f in enumerate(csv_files, 1):
            print(f"{idx}. {f.name}")
        print()

        choice = input("Enter file number (or full path): ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(csv_files):
            csv_path = str(csv_files[int(choice) - 1])
        else:
            csv_path = choice
    else:
        print("No CSV files found in output/")
        csv_path = input("Enter path to links CSV file: ").strip()

    if csv_path:
        max_jobs = input("How many jobs to test? (default: 5): ").strip()
        max_jobs = int(max_jobs) if max_jobs.isdigit() else 5

        asyncio.run(test_phase2_from_csv(csv_path, max_jobs))
    else:
        print("No file specified. Exiting.")
