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

    # Data collected from the job detail page
    scraped_job_title: str = Field(..., description="Full job title from detail page")
    recruiter_name: str = Field(..., description="Name of the recruiter / agency that posted the job")
    job_location_text: str = Field(..., description="Job location address from detail page")
    salary_benefits: str = Field(..., description="Advertised salary and benefits from detail page, if available")
    description_snippet: str = Field(..., description="Job description summary or overview from detail page")
    responsibilities_snippet: str = Field(..., description="Key responsibilities, skills, requirements from detail page")

    # Note: Any field can be an empty string "" if not found on the detail page


def _build_scrape_task(base_url: str, job_title: str, location: str, miles: str) -> str:
    """
    We give browser_use.Agent a deterministic instruction that:
    - Open CVLibrary
    - Enter search criteria
    - Collect ALL job detail page links from ALL pages first
    - Then loop through each link to collect detailed information
    - Return structured JSON matching JobPosting[]
    """
    return f"""
You are a data collection browser agent. You MUST follow these rules exactly in TWO PHASES:

GOAL:
Collect job posting data from CVLibrary.co.uk

=== PHASE 1: COLLECT ALL JOB LINKS ===

STEPS:
1. Go to this URL: {base_url}
2. On the page:
   - Enter the job title: "{job_title}"
   - Enter the location: "{location}"
   - Enter the radius/miles: "{miles}" (miles radius)
   - Start the search.

3. After the search results load, you will see a page with multiple job listing cards displayed vertically.
   Each card has a clickable job title link that goes to the job detail page.

4. COLLECT LINKS FROM PAGE 1:
   - Go through each job card on the page
   - For each card, extract the URL of the job detail page (usually in the job title link)
   - Store all these URLs in a list
   - Scroll down if needed to see all job cards
   - Typically there are 25 jobs per page

5. CHECK FOR MORE PAGES:
   - Look at the bottom of the page for pagination buttons (numbered like "1", "2", "3", "4", "5" or a "Next" button)
   - If there are more pages, click to page 2

6. COLLECT LINKS FROM PAGE 2 (and 3, 4, 5, etc.):
   - Repeat step 4 for this page
   - Add all new job detail URLs to your list
   - Click to the next page (page 3, then 4, then 5, etc.)
   - Continue until there are no more pages

7. After collecting ALL links from ALL pages, you should have a complete list of job detail page URLs.
   For example, if there are 3 pages with 25 jobs each, you should have approximately 75 URLs.

=== PHASE 2: VISIT EACH LINK AND COLLECT DATA ===

8. Now loop through your list of job detail URLs ONE BY ONE:

   For each URL:
   a) Navigate directly to that job detail page URL

   b) On the job detail page, collect the following information:
      1. Full job title → store in scraped_job_title
      2. Company/recruiter name that posted the job → store in recruiter_name
      3. Job location address (e.g. 'Rochester, Kent (England)') → store in job_location_text
      4. Advertised salary for the job → store in salary_benefits
      5. Summary or overview of the job opportunity → store in description_snippet
      6. Key responsibilities, skills, requirements, machinery skills needed, etc. → store in responsibilities_snippet

   c) You may need to scroll down the job detail page to see all information

   d) Move to the next URL in your list and repeat

9. Continue until you have processed ALL URLs from your collected list.

=== HOW TO RETURN DATA ===

10. DO NOT use write_file or any file operations!
    DO NOT create files like job_data.jsonl!
    Keep ALL data in memory and return it as JSON at the end.

    Return your final answer as a JSON list of objects.

Each object MUST include these exact fields:
   - job_id: Generate a fresh UUID4 string for each posting (e.g., "a1b2c3d4-e5f6-7890-1234-567890abcdef")
   - source_url: The job detail page URL you visited (string)
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
    "source_url": "https://www.cv-library.co.uk/job/12345678/senior-software-engineer",
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

IMPORTANT:
   - Do NOT use write_file, save_file, or create any files
   - Do NOT include pagination info
   - Do NOT include ads/sponsored widgets unless they are real job cards
   - Do NOT hallucinate fields you cannot see. Use "" if missing
   - Make sure the JSON you return is valid and parseable
   - In PHASE 1, collect ALL links from ALL pages before starting PHASE 2
   - In PHASE 2, visit each link directly using the URLs you collected

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
    Launches a browser_use.Agent to perform 1 CVLibrary query and scrape ALL pages.
    Uses two-phase approach: collect all job links first, then visit each one.
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
