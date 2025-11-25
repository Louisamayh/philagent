#!/usr/bin/env python3
"""Test the fully dynamic company identification system on 5 jobs"""

import csv
from company_identifier import extract_clues_from_job, identify_potential_companies

# Read the most recent CSV file
csv_file = 'final_output/174a81de-b830-4165-9c16-a62fd6825d7d_jobs_raw.csv'

print("=" * 80)
print("TESTING FULLY DYNAMIC SYSTEM ON 5 JOBS")
print("=" * 80)
print()

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

    results = []

    for idx in range(min(5, len(rows))):
        row = rows[idx]

        print(f"\nJob #{idx+1}: {row['scraped_job_title']}")
        print(f"Location: {row['job_location_text']}")

        # Extract clues
        clues = extract_clues_from_job(
            row['full_job_description'],
            row['scraped_job_title'],
            row['job_location_text']
        )

        postcode = clues.get("location_clues", {}).get("postcode", "") if clues else ""

        # Identify companies
        result = identify_potential_companies(
            clues,
            row['scraped_job_title'],
            row['job_location_text'],
            row['recruiter_name'],
            postcode
        )

        companies = result.get("potential_companies", [])
        cluster = result.get("industrial_cluster", {})
        primary = cluster.get("main_sectors", ["N/A"])[0] if cluster.get("main_sectors") else "N/A"

        print(f"Primary Industry: {primary}")
        print(f"Found {len(companies)} companies")

        if companies:
            print(f"Top: {companies[0].get('company_name')} ({companies[0].get('confidence', 0)*100:.0f}%)")

        results.append({
            'title': row['scraped_job_title'],
            'primary': primary,
            'count': len(companies),
            'top': companies[0].get('company_name') if companies else 'None'
        })

        print("-" * 80)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title'][:40]:<40} | Industry: {r['primary'][:30]:<30} | Companies: {r['count']}")

    print("\n✅ All 5 jobs completed successfully with fully dynamic system!")
