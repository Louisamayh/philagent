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

INPUT_CSV = '/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/1224d045-b920-49a6-895a-1dbd1cf9ec21_jobs_enriched_partial.csv'
OUTPUT_CSV = f'/Users/louisamayhanrahan/code/Ind_Output/philagent/final_output/sample_improved_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
SAMPLE_SIZE = 25

async def process_sample():
    """Process first 25 jobs to validate improvements"""

    # Read input CSV
    print(f"📖 Reading input CSV: {INPUT_CSV}")
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)[:SAMPLE_SIZE]  # Only first 25

    print(f"✓ Processing SAMPLE: {len(rows)} jobs (out of 518 total)\n")

    # Process each row
    enriched_rows = []
    improvements = {'better': 0, 'worse': 0, 'same': 0}

    for idx, row in enumerate(rows, 1):
        job_id = row['job_id']
        job_title = row['scraped_job_title']
        location = row['job_location_text']
        old_company = row['top_company']

        print(f"{'='*80}")
        print(f"[{idx}/{len(rows)}] {job_title} in {location}")
        print(f"{'='*80}")
        print(f"OLD: {old_company}")

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

            # Compare results
            companies = json.loads(enriched.get('potential_companies', '[]'))
            if companies:
                new_company = companies[0].get('company_name', 'N/A')
                new_conf = companies[0].get('confidence', 0)
                print(f"NEW: {new_company} ({new_conf*100:.0f}%)")

                # Simple comparison
                if new_company != old_company:
                    improvements['better'] += 1
                    print("📊 STATUS: CHANGED (likely improved)")
                else:
                    improvements['same'] += 1
                    print("📊 STATUS: Same company")
            else:
                print("NEW: No companies found")
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
    print(f"📊 SAMPLE RESULTS SUMMARY")
    print(f"{'='*80}")
    print(f"Total processed: {len(enriched_rows)}")
    print(f"Changed results: {improvements['better']} ({improvements['better']/len(enriched_rows)*100:.1f}%)")
    print(f"Same results: {improvements['same']}")
    print(f"Errors/No results: {improvements['worse']}")

    if enriched_rows:
        fieldnames = list(enriched_rows[0].keys())
        with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(enriched_rows)

        print(f"\n✅ Sample saved to: {OUTPUT_CSV}")
        print(f"\n💡 Review the sample, then run full batch if improvements look good!")
    else:
        print("❌ No rows to write")

if __name__ == "__main__":
    print("="*80)
    print("🔬 SAMPLE RUN: Testing Improved Search System")
    print("="*80)
    print(f"Processing first {SAMPLE_SIZE} jobs to validate improvements\n")
    print("Improvements tested:")
    print("  ✓ 4-stage technical keyword search")
    print("  ✓ Ultra-specific manufacturing type matching")
    print("  ✓ Machine brand searches (Mazak, Haas, etc.)")
    print("  ✓ Strict filtering (CNC ≠ pressing ≠ fabrication)")
    print("  ✓ Excludes wrong company types (retail, energy, etc.)")
    print()

    asyncio.run(process_sample())
