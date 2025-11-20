#!/usr/bin/env python3
"""
Test script for Phase 2 (Job Scraping) only
Tests scraping job details from a single URL without running Phase 1
"""

import asyncio
from browser_use import ChatGoogle
from job_scraper import scrape_single_job


async def test_single_job():
    """
    Test scraping a single job detail page
    Replace the URL below with a real CV-Library job URL you want to test
    """

    # Initialize LLM
    llm = ChatGoogle(model="gemini-flash-latest")

    # Real CV-Library job URL from your links
    test_url = "https://www.cv-library.co.uk/job/224233708/Mechanical-Design-Engineer?hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143"

    print("=" * 60)
    print("🧪 Testing Phase 2: Job Scraping")
    print("=" * 60)
    print(f"\nTest URL: {test_url}")
    print("\nStarting scrape...\n")

    # Search info (metadata for the job)
    search_info = {
        "job_title": "Test Job Title",
        "location": "Test Location",
        "miles": "30"
    }

    try:
        # Scrape the job
        result = await scrape_single_job(
            llm=llm,
            job_url=test_url,
            search_info=search_info,
            max_steps=50
        )

        print("=" * 60)
        print("✅ RESULTS:")
        print("=" * 60)
        print(f"\nJob ID: {result.get('job_id')}")
        print(f"Source URL: {result.get('source_url')}")
        print(f"Scraped Job Title: {result.get('scraped_job_title')}")
        print(f"Recruiter Name: {result.get('recruiter_name')}")
        print(f"Location: {result.get('job_location_text')}")
        print(f"Salary: {result.get('salary_benefits')}")
        print(f"\nDescription:\n{result.get('description_snippet')[:200]}...")
        print(f"\nResponsibilities:\n{result.get('responsibilities_snippet')[:200]}...")

        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR:")
        print("=" * 60)
        print(f"{str(e)}")
        import traceback
        traceback.print_exc()


async def test_multiple_jobs():
    """
    Test scraping multiple jobs from a list of URLs
    """

    # Initialize LLM
    llm = ChatGoogle(model="gemini-flash-latest")

    # Real CV-Library job URLs from your links
    test_links = [
        {"link_url": "https://www.cv-library.co.uk/job/224233708/Mechanical-Design-Engineer?hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143", "link_text": "Mechanical Design Engineer"},
        {"link_url": "https://www.cv-library.co.uk/job/224255229/Mechanical-Design-Engineer?hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143", "link_text": "Mechanical Design Engineer"},
        {"link_url": "https://www.cv-library.co.uk/job/223778129/Mechanical-Design-Lead?featured=1&hlkw=mechanical-design-engineer&sid=e765253a-919b-4b31-a79e-17ddecb4f143", "link_text": "Mechanical Design Lead"},
    ]

    print("=" * 60)
    print("🧪 Testing Phase 2: Multiple Jobs")
    print("=" * 60)
    print(f"\nTesting {len(test_links)} jobs\n")

    search_info = {
        "job_title": "Test Job Title",
        "location": "Test Location",
        "miles": "30"
    }

    results = []

    for idx, link in enumerate(test_links, 1):
        print(f"\n[{idx}/{len(test_links)}] Scraping: {link['link_url']}")

        try:
            result = await scrape_single_job(
                llm=llm,
                job_url=link['link_url'],
                search_info=search_info,
                max_steps=50
            )
            results.append(result)
            print(f"✅ Scraped: {result.get('scraped_job_title', 'N/A')}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            continue

    print("\n" + "=" * 60)
    print(f"✅ Scraped {len(results)}/{len(test_links)} jobs successfully")
    print("=" * 60)


if __name__ == "__main__":
    print("\n🚀 Phase 2 Test Script\n")
    print("Choose test mode:")
    print("1. Test single job URL")
    print("2. Test multiple job URLs")
    print()

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        asyncio.run(test_single_job())
    elif choice == "2":
        asyncio.run(test_multiple_jobs())
    else:
        print("Invalid choice. Please run again and choose 1 or 2.")
