#!/usr/bin/env python3
"""Test the full pipeline with web search"""

import json
from company_identifier import identify_potential_companies, extract_clues_from_job

# Test job data
job_title = "CNC Machinist"
location = "Leicester, Leicestershire"
postcode = "LE4"
recruiter_name = "Engineering Recruitment Ltd"
job_description = """
An established aerospace manufacturer in Leicester is seeking an experienced CNC Machinist.

Role Requirements:
- 5-axis CNC machining experience
- Fanuc control systems
- Working with aerospace alloys (titanium, inconel)
- AS9100 quality standards
- Reading engineering drawings

The Company:
- Family-owned business established 1985
- Aerospace & defence sector
- Modern facility with latest CNC equipment
- Salary £35,000 - £42,000
"""

print("=" * 80)
print("TESTING FULL PIPELINE WITH WEB SEARCH")
print("=" * 80)
print(f"\nJob: {job_title}")
print(f"Location: {location}")
print(f"Postcode: {postcode}")

# Extract clues
print("\n" + "=" * 80)
print("STEP 1: EXTRACTING CLUES")
print("=" * 80)
clues = extract_clues_from_job(
    job_description=job_description,
    job_title=job_title,
    location=location
)
print(json.dumps(clues, indent=2)[:500] + "...")

# Identify companies (with web search)
print("\n" + "=" * 80)
print("STEP 2: IDENTIFYING COMPANIES (WITH WEB SEARCH)")
print("=" * 80)
result = identify_potential_companies(
    clues=clues,
    job_title=job_title,
    location=location,
    recruiter_name=recruiter_name,
    postcode=postcode
)

print("\n📊 COMPANY IDENTIFICATION RESULTS:")
print("=" * 80)
if result.get('potential_companies'):
    for idx, company in enumerate(result['potential_companies'], 1):
        print(f"\n{idx}. {company.get('company_name', 'N/A')}")
        print(f"   Postcode: {company.get('company_postcode', 'N/A')}")
        print(f"   Match: {'✓' if company.get('postcode_matches_job') else '✗'}")
        print(f"   Score: {company.get('total_score', 0)}/60")
        print(f"   Confidence: {company.get('confidence', 0)*100:.0f}%")
        print(f"   Reasoning: {company.get('reasoning', 'N/A')[:150]}...")
else:
    print("No companies identified")

print(f"\n🌍 Industrial Cluster: {result.get('industrial_cluster', {}).get('location', 'N/A')}")
print(f"   Sectors: {', '.join(result.get('industrial_cluster', {}).get('main_sectors', []))}")

print("\n" + "=" * 80)
print("✅ FULL PIPELINE TEST COMPLETE!")
print("=" * 80)
