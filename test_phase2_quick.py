#!/usr/bin/env python3
"""
Quick test of Phase 2 using real job links from your CSV
"""

import asyncio
from browser_use import ChatGoogle
from job_scraper import scrape_single_job


async def test_phase2():
    """Test Phase 2 with real job links"""

    # Initialize LLM
    llm = ChatGoogle(model="gemini-flash-latest")

    # Real job links from your CSV
    test_links = [
        "https://www.cv-library.co.uk/job/224233708/Mechanical-Design-Engineer?hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143",
        "https://www.cv-library.co.uk/job/224255229/Mechanical-Design-Engineer?hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143",
        "https://www.cv-library.co.uk/job/223778129/Mechanical-Design-Lead?featured=1&hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143",
    ]

    # Search info from the CSV
    search_info = {
        "job_title": "mechanical design engineer",
        "location": "Leicester",
        "miles": "35"
    }

    print("=" * 60)
    print("🧪 Testing Phase 2: Job Scraping")
    print("=" * 60)
    print(f"Search: {search_info['job_title']} in {search_info['location']}")
    print(f"Testing {len(test_links)} jobs\n")

    results = []

    for idx, job_url in enumerate(test_links, 1):
        print(f"\n[{idx}/{len(test_links)}] Scraping:")
        print(f"   URL: {job_url}")

        try:
            result = await scrape_single_job(
                llm=llm,
                job_url=job_url,
                search_info=search_info,
                max_steps=50
            )
            results.append(result)

            print(f"   ✅ {result.get('scraped_job_title', 'N/A')}")
            print(f"      Recruiter: {result.get('recruiter_name', 'N/A')}")
            print(f"      Location: {result.get('job_location_text', 'N/A')}")
            print(f"      Salary: {result.get('salary_benefits', 'N/A')}")

        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "=" * 60)
    print(f"✅ Successfully scraped {len(results)}/{len(test_links)} jobs")
    print("=" * 60)

    # Show detailed results
    if results:
        print("\n📊 DETAILED RESULTS:\n")
        for idx, result in enumerate(results, 1):
            print(f"\n--- Job {idx} ---")
            print(f"Job ID: {result.get('job_id')}")
            print(f"Title: {result.get('scraped_job_title')}")
            print(f"Recruiter: {result.get('recruiter_name')}")
            print(f"Location: {result.get('job_location_text')}")
            print(f"Salary: {result.get('salary_benefits')}")
            print(f"\nDescription (first 300 chars):")
            print(result.get('description_snippet', '')[:300])
            print(f"\nResponsibilities (first 300 chars):")
            print(result.get('responsibilities_snippet', '')[:300])


if __name__ == "__main__":
    print("\n🚀 Phase 2 Quick Test\n")
    asyncio.run(test_phase2())
