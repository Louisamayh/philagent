#!/usr/bin/env python3
"""Test Panel Wirer job - should find machine builders, NOT retail/energy"""

import json
from company_identifier import identify_potential_companies, extract_clues_from_job

# Panel Wirer job from user's example
job_title = "Panel Wirer"
location = "Leicester"
postcode = "LE8"
recruiter_name = "Engineering Recruitment"
job_description = """
Panel Wirer required for our client based in LE8.

You will be working on machine wiring and control panel building for special purpose machinery.

Requirements:
- Reading wiring schematics
- 3-phase industrial equipment experience
- Contactors, relays, PLCs
- Workshop-based role
- Machine building industry experience preferred

£22 per hour CIS
Day shift, early finish Friday
"""

print("=" * 80)
print("TESTING PANEL WIRER JOB - Should find MACHINE BUILDERS, not retail/energy")
print("=" * 80)
print(f"\nJob: {job_title}")
print(f"Location: {location}, {postcode}")

# Extract clues
print("\n" + "=" * 80)
print("STEP 1: EXTRACTING CLUES")
print("=" * 80)
clues = extract_clues_from_job(
    job_description=job_description,
    job_title=job_title,
    location=location
)
print(json.dumps(clues, indent=2)[:800] + "...")

# Identify companies
print("\n" + "=" * 80)
print("STEP 2: IDENTIFYING COMPANIES (WITH TECHNICAL KEYWORD SEARCH)")
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
        company_name = company.get('company_name', 'N/A')
        company_postcode = company.get('company_postcode', 'N/A')
        score = company.get('total_score', 0)
        confidence = company.get('confidence', 0)

        # Check if it's a wrong company type
        wrong_type = ""
        if any(word in company_name.lower() for word in ['retail', 'energy', 'recruitment']):
            wrong_type = " ⚠️ WRONG TYPE!"

        print(f"\n{idx}. {company_name}{wrong_type}")
        print(f"   Postcode: {company_postcode}")
        print(f"   Match: {'✓' if company.get('postcode_matches_job') else '✗'}")
        print(f"   Score: {score}/60")
        print(f"   Confidence: {confidence*100:.0f}%")
        print(f"   Source: {company.get('source_search_result', 'N/A')[:80]}...")
        print(f"   Reasoning: {company.get('reasoning', 'N/A')[:200]}...")
else:
    print("No companies identified")

print("\n" + "=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
print("\n🎯 Expected companies: Aylmer Automation, CME Ltd, Laintec, Techni Systems")
print("❌ Should NOT find: Siya Retail, Jarvis Energy, recruitment agencies")
