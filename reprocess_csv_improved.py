#!/usr/bin/env python3
"""
Re-process CSV with improved web search and company identification
"""

import csv
import json
import asyncio
from datetime import datetime
from company_identifier import enrich_posting_with_company_id

INPUT_CSV = '/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/1224d045-b920-49a6-895a-1dbd1cf9ec21_jobs_enriched_partial.csv'
OUTPUT_CSV = f'/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/reprocessed_improved_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

async def process_csv():
    """Process all rows in CSV with improved company identification"""

    # Read input CSV
    print(f"📖 Reading input CSV: {INPUT_CSV}")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"✓ Found {len(rows)} jobs to process\n")

    # Process each row
    enriched_rows = []
    for idx, row in enumerate(rows, 1):
        job_id = row['job_id']
        job_title = row['scraped_job_title']
        location = row['job_location_text']

        print(f"{'='*80}")
        print(f"[{idx}/{len(rows)}] Processing: {job_title} in {location}")
        print(f"{'='*80}")

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

            # Show summary
            companies = json.loads(enriched.get('potential_companies', '[]'))
            print(f"\n✅ Found {len(companies)} companies:")
            for i, comp in enumerate(companies[:3], 1):
                print(f"   {i}. {comp.get('company_name', 'N/A')} ({comp.get('confidence', 0)*100:.0f}%)")
            print()

        except Exception as e:
            print(f"❌ Error processing {job_id}: {e}")
            enriched_rows.append(posting)

        # Small delay to avoid rate limiting
        if idx < len(rows):
            await asyncio.sleep(2)

    # Write output CSV
    print(f"\n{'='*80}")
    print(f"📝 Writing results to: {OUTPUT_CSV}")
    print(f"{'='*80}")

    if enriched_rows:
        fieldnames = list(enriched_rows[0].keys())
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)

        print(f"✅ Successfully processed {len(enriched_rows)} jobs!")
        print(f"📁 Output saved to: {OUTPUT_CSV}")
    else:
        print("❌ No rows to write")

if __name__ == "__main__":
    print("="*80)
    print("🔄 RE-PROCESSING CSV WITH IMPROVED SEARCH SYSTEM")
    print("="*80)
    print("\nImprovements:")
    print("  ✓ 4-stage technical keyword search")
    print("  ✓ Ultra-specific manufacturing type matching")
    print("  ✓ Machine brand searches (Mazak, Haas, etc.)")
    print("  ✓ Strict filtering (CNC ≠ pressing ≠ fabrication)")
    print("  ✓ Excludes wrong company types")
    print()

    asyncio.run(process_csv())
