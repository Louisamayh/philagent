import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle

# Set up file logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)


class JobPosting(BaseModel):
    # Metadata to keep traceability
    job_id: str = Field(..., description="Unique ID for this scraped posting, UUID4")
    source_url: str = Field(..., description="The CVLibrary URL that was opened for this search")

    # The search inputs that produced this page of listings
    search_job_title: str
    search_location: str
    search_radius_miles: str

    # Data visible directly on the results page card (NO clicking into details)
    scraped_job_title: str = Field(..., description="Job title text shown on the listing card")
    recruiter_name: str = Field(..., description="Name of the recruiter / agency shown on the card")
    job_location_text: str = Field(..., description="Location text shown on the card")
    salary_benefits: str = Field(..., description="Salary / benefits text shown on the card, if available")
    description_snippet: str = Field(..., description="Short job description snippet or summary visible on card")
    responsibilities_snippet: str = Field(..., description="Key responsibilities or duties visible on card")

    # (Optional in case card doesn't show responsibilities separately)
    # responsibilities_snippet can be "" if not present.


def _build_scrape_task(base_url: str, job_title: str, location: str, miles: str) -> str:
    """
    We give browser_use.Agent a deterministic instruction that:
    - Open CVLibrary
    - Enter search criteria
    - Scrape ONLY what's visible on the search results page
    - Return structured JSON matching JobPosting[]
    """
    return f"""
You are a data collection browser agent. You MUST follow these rules exactly, first we are giving you some contaxt and then you will find your instructions:

GOAL:
Collect job posting data from CVLibrary.co.uk details below.

Pt 1: Context 

SCROLLING: You may need to scroll to find all the information you require, scroll slowly, ONCE or TWICE, then pause and check for the new content. Then you can scroll again if you need to.
   STOP scrolling if:
   - The page doesn't move when you try to scroll (you're at the bottom)

TRACKING STRATEGY - Each job listing can be quite similar. We need you to open each joblisting one at a time. So you do not get lost, use unique URLs to avoid duplicates:
   - Maintain a list of job detail page URLs you have already visited
   - Each job detail page has a unique URL
   - Before clicking a job, check if you've already visited its detail page URL
   - Only click jobs you haven't visited yet
   - The jobs are in list format so please start from the top and work your way down.
   NOTE: Job titles, recruiters, and locations may be similar or identical - the URL is the unique identifier.


Context:
You will be searching for jobs on CVLibrary.co.uk, when you reach the job listings page, you will see multiple job cards displayed vertically. There is 25 jobs per page typically. To get to the next page of results, you will need to click the pagination buttons at the bottom of the page (e.g. "2", "3", or "Next").

Part 2: Step by Step Instructions  to follow EXACTLY:

To start: 

STEPS:
1. Go to this URL: {base_url}
2. On the page:
   - Enter the job title: "{job_title}"
   - Enter the location: "{location}"
   - Enter the radius/miles: "{miles}" (miles radius)
   - Start the search.

3. After the search results load, you will see a page with multiple job listing cards displayed vertically. This is the "job listing page".

4. (one time only) SAVE THE LISTINGS PAGE URL:
   - Record the current URL of the search results page (the page showing all the job cards)
   - If at some point you cant navigate back to the job listing tab, you can use this URL to navigate back after viewing each job detail page
   - This is your "home base" URL that you can return to if needs be.


5. ON THE JOB LISTING PAGE, do the following FOR EACH JOB:

   a) Make sure you are on the correct job listings page (if not, navigate to the saved listings URL)

   b) Identify the job listing card you need to process:
      - For the FIRST job: Start with the top-most job listing card
      - For subsequent jobs: Find the card directly BELOW the one you just completed

   c) BEFORE CLICKING - Read and remember the description snippet visible on THIS card:
      - Note down the job description text shown on the listing card
      - This will help you verify your position when you return to the listings page

   d) Click that job's "title" link to open the "job detail page" (may open in a new tab)

   e) On the job detail page:
      - Record/remember the current page URL (this is the unique identifier for this job)
      - The information you need will be throughout the page, you may need to scroll to see everything

   f) Collect the following information from the detail page:
      1. Full job title → store in scraped_job_title
      2. Company/recruiter name that posted the job → store in recruiter_name
      3. Job location address (e.g. 'Rochester, Kent (England)') → store in job_location_text
      4. Advertised salary for the job → store in salary_benefits
      5. Summary or overview of the job opportunity → store in description_snippet
      6. Key responsibilities, skills, requirements, machinery skills needed, etc. → store in responsibilities_snippet

   g) Return to the job listings page (navigate back to your saved "home base" URL if needed)

   h) Find the NEXT job listing to process:
      - The next job should be directly BELOW the one you just completed
      - You may need to scroll down slightly to see it
      - VERIFY you have the correct card: Look at the card ABOVE your selected card - its description should match the description you noted in step (c)
      - If the descriptions don't match, scroll up/down to find the correct card

   i) Repeat steps (c) through (h) for each job listing, working your way down the list one at a time

   j) Continue until you have processed ALL job listings on this page (typically 25 jobs per page)


6. After scraping all jobs on page 1, check for numbered buttoms at the bottom of the job listing page (numbered buttons like "1", "2", "3" or a "Next" button):
   - Click "2" (or "Next") to go to page 2
   - SAVE this new page's URL as your new "home base" listings URL ** if you get lost you can use this URL to return to this page ** However if you can't navigate back to this page, you can always return to the original search URL from step 1 and re-enter the search criteria to get back to page 1, then click "2" to get to page 2.
   - Repeat steps 5 for all jobs on page 2
   - 0nce finished anaylsing all job details on page two repeat step five except click button, 3 after 3 is completed click 4, etc. until there are no more pages, updating your "home base" URL each time

8. ⚠️ CRITICAL - HOW TO RETURN DATA ⚠️:

   DO NOT use write_file or any file operations!
   DO NOT create files like job_data.jsonl!
   Keep ALL data in memory and return it as JSON at the end.

   Return your final answer as a JSON list of objects.

Each object MUST include these exact fields:
   - job_id: Generate a fresh UUID4 string for each posting (e.g., "a1b2c3d4-e5f6-7890-1234-567890abcdef")
   - source_url: The search results page URL (string)
   - search_job_title: The exact string "{job_title}"
   - search_location: The exact string "{location}"
   - search_radius_miles: The exact string "{miles}"
   - scraped_job_title: The job title text you found on the detail page (string, empty string "" if not found)
   - recruiter_name: The recruiter/company name you found (string, empty string "" if not found)
   - job_location_text: The location text you found (string, empty string "" if not found)
   - salary_benefits: The salary/benefits text you found (string, empty string "" if not found)
   - description_snippet: The job description/summary you found (string, empty string "" if not found)
   - responsibilities_snippet: The responsibilities/requirements you found (string, empty string "" if not found)

EXAMPLE of one complete object:
{{
    "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "source_url": "https://www.cv-library.co.uk/search-jobs?q=engineer&geo=london&distance=10",
    "search_job_title": "{job_title}",
    "search_location": "{location}",
    "search_radius_miles": "{miles}",
    "scraped_job_title": "Senior Software Engineer",
    "recruiter_name": "TechRecruit Ltd",
    "job_location_text": "London, Greater London",
    "salary_benefits": "£60,000 - £80,000 per annum",
    "description_snippet": "We are looking for an experienced software engineer to join our growing team...",
    "responsibilities_snippet": "Design and develop software solutions, mentor junior developers, participate in code reviews..."
}}

9. IMPORTANT:
   - Do NOT use write_file, save_file, or create any files
   - Do NOT include pagination info.
   - Do NOT include ads/sponsored widgets unless they are real job cards.
   - Do NOT hallucinate fields you cannot see. Use "" if missing.
   - Make sure the JSON you return is valid and parseable.

Your ONLY output should be that JSON list of job posting objects - NO FILE OPERATIONS!
"""


async def scrape_search_row(
    llm: ChatGoogle,
    base_url: str,
    job_title: str,
    location: str,
    miles: str,
    max_steps: int = 40,
) -> List[dict]:
    """
    Launches a browser_use.Agent to perform 1 CVLibrary query and scrape the first page.
    Returns a list of dicts (each one matches JobPosting schema).
    """

    # We'll ask browser_use to produce JobPosting[] (list of JobPosting)
    # Note: browser_use currently supports output_model_schema for a SINGLE object,
    # so we will parse agent.run().final_result() manually as JSON list.
    task = _build_scrape_task(base_url, job_title, location, miles)

    agent = Agent(
        task=task,
        llm=llm,
        step_timeout=120,
        max_actions_per_step=8,
        max_failures=5,  # Increased from 2 to allow more retries
        # We are NOT passing output_model_schema here because we want list[...] not single obj.
        # Disable file operations to force agent to return JSON directly
        # use_vision=True,  # Keep vision enabled for reading page content
    )

    logger.info(f"=" * 60)
    logger.info(f"Starting scrape for: {job_title} in {location} ({miles} miles)")
    logger.info(f"Max steps: {max_steps}")
    print(f"Starting scrape for: {job_title} in {location} ({miles} miles)")
    print(f"Max steps: {max_steps}")

    try:
        history = await agent.run(max_steps=max_steps)
        steps_used = len(history.history) if hasattr(history, 'history') else 'unknown'
        logger.info(f"Agent completed. Total steps used: {steps_used}")
        print(f"Agent completed. Total steps used: {steps_used}")
    except Exception as e:
        logger.error(f"Agent.run() failed with exception: {e}")
        print(f"ERROR: Agent.run() failed with exception: {e}")
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
        return []

    # browser_use Agent returns 'final_result()' as text OR 'structured_output'
    # We'll try both.
    result_json_str = None
    result_json = []  # Initialize to empty list

    # try structured_output first
    logger.debug("Checking for structured_output...")
    if hasattr(history, "structured_output") and history.structured_output:
        logger.debug(f"Found structured_output (type: {type(history.structured_output)})")
        # structured_output might already be a python object (list[dict]) or a string
        if isinstance(history.structured_output, list):
            result_json = history.structured_output
            logger.info(f"structured_output is list with {len(result_json)} items")
        elif isinstance(history.structured_output, str):
            result_json_str = history.structured_output
            logger.debug(f"structured_output is string (length {len(result_json_str)})")
            logger.debug(f"First 500 chars: {result_json_str[:500]}")
        else:
            logger.warning(f"structured_output is unexpected type, will try final_result()")
            result_json_str = None
    else:
        logger.debug("No structured_output, trying final_result()...")
        # try final_result()
        try:
            fr = history.final_result()
            logger.debug(f"final_result() returned (type: {type(fr)})")
        except Exception as e:
            logger.debug(f"final_result() raised: {e}")
            fr = None

        if isinstance(fr, str):
            result_json_str = fr
            logger.debug(f"final_result is string (length {len(result_json_str)})")
            logger.debug(f"First 500 chars: {result_json_str[:500]}")
        else:
            logger.warning(f"final_result is not a string (type: {type(fr)}), cannot parse")
            result_json_str = None

    if result_json_str is not None:
        import json
        logger.debug("Attempting to parse JSON...")
        try:
            result_json = json.loads(result_json_str)
            logger.info(f"JSON parsed successfully (type: {type(result_json)})")
        except Exception as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw string (first 1000 chars): {result_json_str[:1000]}")
            result_json = []

    # result_json should now be a python list of dicts
    if not isinstance(result_json, list):
        logger.error(f"Agent did not return a list. Got type: {type(result_json)}")
        logger.debug(f"Value: {str(result_json)[:500]}")
        return []

    logger.info(f"✓ Agent returned {len(result_json)} raw job postings")

    # final cleanup / ensure required fields exist
    cleaned: List[dict] = []
    for item in result_json:
        # force UUID if missing or blank
        item_job_id = item.get("job_id") or str(uuid.uuid4())
        cleaned.append(
            {
                "job_id": item_job_id,
                "source_url": item.get("source_url", base_url),

                "search_job_title": item.get("search_job_title", job_title),
                "search_location": item.get("search_location", location),
                "search_radius_miles": item.get("search_radius_miles", miles),

                "scraped_job_title": item.get("scraped_job_title", ""),
                "recruiter_name": item.get("recruiter_name", ""),
                "job_location_text": item.get("job_location_text", ""),
                "salary_benefits": item.get("salary_benefits", ""),
                "description_snippet": item.get("description_snippet", ""),
                "responsibilities_snippet": item.get("responsibilities_snippet", ""),
            }
        )

    logger.info(f"✓ Returning {len(cleaned)} cleaned job postings")
    logger.info(f"Log file: {log_file}")

    if len(cleaned) == 0:
        logger.warning("No job postings were successfully scraped!")
        logger.warning("This could mean:")
        logger.warning("  - The agent couldn't navigate to CVLibrary")
        logger.warning("  - The agent got stuck and hit max_steps")
        logger.warning("  - The agent couldn't find/extract job listings")
        logger.warning("  - The website structure changed")
        logger.warning(f"Check the full log at: {log_file}")

    return cleaned
