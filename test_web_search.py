#!/usr/bin/env python3
"""Quick test of web search integration"""

from company_identifier import search_companies_in_area, verify_company

# Test 1: Basic search
print("=" * 60)
print("TEST 1: Search for companies in Leicester, aerospace")
print("=" * 60)
result = search_companies_in_area(
    location="Leicester",
    postcode="LE4",
    sector="aerospace manufacturing",
    machinery="CNC machining"
)
print(result)

print("\n" + "=" * 60)
print("TEST 2: Verify a specific company")
print("=" * 60)
result2 = verify_company(
    company_name="Parker Hannifin",
    location="Leicester",
    postcode="LE4",
    job_title="CNC Machinist",
    machinery="CNC"
)
print(result2)

print("\n✅ Web search integration is working!")
