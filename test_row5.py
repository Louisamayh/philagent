#!/usr/bin/env python3
"""Test Row 5 - CNC Setter/Operator with improved search"""

import json
from company_identifier import identify_potential_companies, extract_clues_from_job

# Row 5 from CSV
job_title = "CNC setter / operator"
location = "Leicester, Leicestershire (LE4 area)"
postcode = "LE4"
recruiter_name = "Precision People"
job_description = """
Permanent Opportunity
Paying upto £17.00 p/h
Permanent role based in the LE4 area of Leicester, commutable from Queniborough, Syston, Thurmaston, East Goscote and surrounding areas
Our client is looking for an experienced CNC Setter / Operator with experience operating a CNC Milling Machine
Interviewing immediate
Working a day shift Monday to Thursday 06.30 - 16.45
Overtime paid at a premium
JOB PURPOSE
To report to the Machine Shop Supervisor
To set and Operate a CNC Milling Machine
"""

print("=" * 80)
print("TESTING ROW 5 - CNC Setter/Operator")
print("=" * 80)
print(f"Job: {job_title}")
print(f"Location: {location}")
print(f"\n❌ OLD RESULTS (WRONG):")
print("   - Hamilton Adhesive Labels Ltd (82%) - Label printing, not CNC machining!")
print("   - Lestercast Ltd (75%)")
print("   - Formwell Plastics Ltd (70%) - Plastics, not CNC shop")

# Extract clues
print("\n" + "=" * 80)
print("EXTRACTING CLUES WITH IMPROVED SYSTEM")
print("=" * 80)
clues = extract_clues_from_job(
    job_description=job_description,
    job_title=job_title,
    location=location
)

# Identify companies
print("\n" + "=" * 80)
print("IDENTIFYING COMPANIES WITH NEW 4-STAGE TECHNICAL SEARCH")
print("=" * 80)
result = identify_potential_companies(
    clues=clues,
    job_title=job_title,
    location=location,
    recruiter_name=recruiter_name,
    postcode=postcode
)

print("\n📊 NEW RESULTS:")
print("=" * 80)
if result.get('potential_companies'):
    for idx, company in enumerate(result['potential_companies'], 1):
        company_name = company.get('company_name', 'N/A')
        company_postcode = company.get('company_postcode', 'N/A')
        score = company.get('total_score', 0)
        confidence = company.get('confidence', 0)

        print(f"\n{idx}. {company_name}")
        print(f"   Postcode: {company_postcode}")
        print(f"   Score: {score}/60 ({confidence*100:.0f}%)")
        print(f"   Reasoning: {company.get('reasoning', 'N/A')[:200]}...")
else:
    print("No companies identified")

print("\n" + "=" * 80)
print("✅ COMPARISON")
print("=" * 80)
print("Expected: CNC machining/precision engineering companies in LE4")
print("Should NOT find: Label printing, plastics companies")
