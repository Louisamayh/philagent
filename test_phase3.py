#!/usr/bin/env python3
"""
Quick test script for Phase 3 company identification
Reads from an existing Phase 2 CSV and runs company identification
"""

import asyncio
import csv
from pathlib import Path
from company_identifier import enrich_postings_with_company_identification


def read_phase2_csv(csv_path: str):
    """Read Phase 2 job data from CSV"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


async def test_phase3(phase2_csv_path: str, max_jobs: int = 3):
    """
    Test Phase 3 on existing Phase 2 data

    Args:
        phase2_csv_path: Path to Phase 2 CSV (e.g., "final_output/xxx_jobs_raw.csv")
        max_jobs: Maximum number of jobs to test (default: 3 for quick testing)
    """

    print(f"🧪 Testing Phase 3 Company Identification")
    print(f"=" * 60)

    # Check if file exists
    if not Path(phase2_csv_path).exists():
        print(f"❌ Error: File not found: {phase2_csv_path}")
        print("\nAvailable Phase 2 files:")
        output_dir = Path("final_output")
        if output_dir.exists():
            for f in output_dir.glob("*_jobs_raw.csv"):
                print(f"  - {f}")
        return

    # Read Phase 2 data
    print(f"📄 Reading Phase 2 data from: {phase2_csv_path}")
    jobs = read_phase2_csv(phase2_csv_path)

    if not jobs:
        print("❌ No jobs found in CSV")
        return

    # Limit to max_jobs for testing
    jobs = jobs[:max_jobs]
    print(f"✅ Testing with {len(jobs)} jobs\n")

    # Run Phase 3
    print("🔍 Starting company identification...")
    print("=" * 60)

    enriched = await enrich_postings_with_company_identification(jobs)

    print("\n" + "=" * 60)
    print(f"✅ Completed {len(enriched)} jobs")
    print("=" * 60)

    # Display results
    for idx, result in enumerate(enriched, 1):
        print(f"\n--- Job {idx} ---")
        print(f"Job Title: {result.get('scraped_job_title', 'N/A')}")
        print(f"Location: {result.get('job_location_text', 'N/A')}")
        print(f"Recruiter: {result.get('recruiter_name', 'N/A')}")
        print(f"\n🎯 Top Company: {result.get('top_company', 'N/A')}")
        print(f"   Confidence: {result.get('top_confidence', 0)*100:.0f}%")
        print(f"\n📋 Analysis: {result.get('analysis_summary', 'N/A')[:200]}...")

        # Show potential companies
        import json
        try:
            companies = json.loads(result.get('potential_companies', '[]'))
            if companies:
                print(f"\n🏢 All Potential Companies:")
                for company in companies:
                    print(f"   - {company.get('company_name', 'N/A')} ({company.get('confidence', 0)*100:.0f}%)")
        except:
            pass

    # Save results
    output_path = "output/phase3_test_results.csv"
    Path(output_path).parent.mkdir(exist_ok=True)

    fieldnames = [
        "job_id", "scraped_job_title", "recruiter_name", "job_location_text",
        "full_job_description", "extracted_clues", "industrial_cluster", "cluster_summary",
        "potential_companies", "all_companies_readable", "analysis_summary",
        "top_company", "top_confidence", "top_score"
    ]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)

    print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    import sys

    print("\n🚀 Phase 3 Test Script\n")

    # Check for existing Phase 2 files
    output_dir = Path("final_output")
    csv_files = []

    if output_dir.exists():
        csv_files = list(output_dir.glob("*_jobs_raw.csv"))

    if csv_files:
        print("Available Phase 2 CSV files:")
        for idx, f in enumerate(csv_files, 1):
            # Show file size and modification time
            size = f.stat().st_size / 1024  # KB
            print(f"{idx}. {f.name} ({size:.1f} KB)")
        print()

        if len(sys.argv) > 1:
            csv_path = sys.argv[1]
        else:
            choice = input("Enter file number (or full path): ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(csv_files):
                csv_path = str(csv_files[int(choice) - 1])
            else:
                csv_path = choice
    else:
        print("No Phase 2 CSV files found in final_output/")
        csv_path = input("Enter path to Phase 2 CSV file: ").strip()

    if csv_path:
        max_jobs = input("How many jobs to test? (default: 3): ").strip()
        max_jobs = int(max_jobs) if max_jobs.isdigit() else 3

        asyncio.run(test_phase3(csv_path, max_jobs))
    else:
        print("No file specified. Exiting.")
