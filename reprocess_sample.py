#!/usr/bin/env python3
"""
Re-process SAMPLE (first 25 jobs) with improved search system
Quick validation of improvements before full run
"""

import csv
import json
import asyncio
from datetime import datetime
from company_identifier import enrich_posting_with_company_id

INPUT_CSV = '/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/4741cba6-2f3d-4bc2-b8c9-fdcf64665be5_jobs_raw.csv'
OUTPUT_CSV = f'/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/rows_5_to_8_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
# Test rows 5, 6, 7, 8 (indices 4, 5, 6, 7)
START_ROW = 4
END_ROW = 8

async def process_sample():
    """Process rows 5-8 to test improvements"""

    # Read input CSV
    print(f"📖 Reading input CSV: {INPUT_CSV}")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)
        rows = all_rows[START_ROW:END_ROW]  # Rows 5-8 (indices 4-7)

    print(f"✓ Processing rows {START_ROW+1}-{END_ROW}: {len(rows)} jobs (out of {len(all_rows)} total)\n")

    # Process each row
    enriched_rows = []
    improvements = {'better': 0, 'worse': 0, 'same': 0}

    for idx, row in enumerate(rows, 1):
        job_id = row['job_id']
        job_title = row['scraped_job_title']
        location = row['job_location_text']

        print(f"{'='*80}")
        print(f"[ROW {START_ROW+idx}] {job_title} in {location}")
        print(f"{'='*80}")
        print(f"Recruiter: {row.get('recruiter_name', 'N/A')}")

        # Prepare posting dict
        posting = {
            'job_id': job_id,
            'scraped_job_title': job_title,
            'job_location_text': location,
            'recruiter_name': row['recruiter_name'],
            'full_job_description': row['full_job_description']
        }

        try:
            # Process with improved system
            enriched = await enrich_posting_with_company_id(posting)
            enriched_rows.append(enriched)

            # Display results
            companies = json.loads(enriched.get('potential_companies', '[]'))
            if companies:
                print(f"\n📊 RESULTS: Found {len(companies)} potential companies")
                for i, company in enumerate(companies[:3], 1):  # Show top 3
                    print(f"  {i}. {company.get('company_name', 'N/A')} ({company.get('confidence', 0)*100:.0f}%, Score: {company.get('total_score', 0)}/60)")
                    print(f"     Industry Source: {company.get('industry_source', 'N/A')}")
                    print(f"     Is Manufacturer: {company.get('is_manufacturer', 'N/A')}")
                improvements['better'] += 1
            else:
                print("\n❌ No companies found")
                improvements['worse'] += 1

            print()

        except Exception as e:
            print(f"❌ Error: {e}\n")
            enriched_rows.append(posting)
            improvements['worse'] += 1

        # Small delay
        if idx < len(rows):
            await asyncio.sleep(1)

    # Write output CSV
    print(f"\n{'='*80}")
    print(f"📊 TEST RESULTS SUMMARY (Rows 5-8)")
    print(f"{'='*80}")
    print(f"Total processed: {len(enriched_rows)}")
    print(f"Successful: {improvements['better']}")
    print(f"Errors/No results: {improvements['worse']}")

    if enriched_rows:
        fieldnames = list(enriched_rows[0].keys())
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)

        print(f"\n✅ Results saved to: {OUTPUT_CSV}")
    else:
        print("❌ No rows to write")

if __name__ == "__main__":
    print("="*80)
    print("🧪 TESTING ROWS 5, 6, 7, 8 with Updated Code")
    print("="*80)
    print(f"Processing rows {START_ROW+1}-{END_ROW} from the raw jobs CSV\n")
    print("Testing updated company_identifier.py code changes\n")

    asyncio.run(process_sample())
