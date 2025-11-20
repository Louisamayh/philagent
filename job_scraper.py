"""
Phase 2: Job Detail Scraper
Visits each job detail page URL and extracts full job information
"""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle
import json

# Set up file logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"job_scraping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class JobPosting(BaseModel):
    """Job posting with full details scraped from detail page"""
    job_id: str = Field(..., description="Unique ID for this scraped posting, UUID4")
    source_url: str = Field(..., description="The job detail page URL")
    search_job_title: str
    search_location: str
    search_radius_miles: str
    scraped_job_title: str = Field(..., description="Full job title from detail page")
    recruiter_name: str = Field(..., description="Name of the recruiter / agency that posted the job")
    job_location_text: str = Field(..., description="Job location address from detail page")
    salary_benefits: str = Field(..., description="Advertised salary and benefits from detail page, if available")
    full_job_description: str = Field(..., description="COMPLETE job description - every word from the job posting page, including all details, requirements, benefits, etc.")
    description_snippet: str = Field(..., description="Job description summary or overview from detail page")
    responsibilities_snippet: str = Field(..., description="Key responsibilities, skills, requirements from detail page")


def _build_job_scrape_task(job_url: str, search_info: Dict[str, str]) -> str:
    """
    Instructions for Phase 2: Scrape one job detail page
    """
    return f"""
You are a job detail scraper. Your job is to extract information from a single job posting detail page.

=== YOUR TASK ===

Visit this job detail page and extract all available information:
URL: {job_url}

=== INSTRUCTIONS ===

1. Navigate directly to the URL above

2. On the job detail page, extract the following information:
   - Full job title
   - Company/recruiter name that posted the job
   - Job location (full address if available, e.g., 'Rochester, Kent (England)')
   - Advertised salary and benefits
   - **COMPLETE job description - EVERY WORD from the entire job posting** (scroll down to get ALL text)
   - Job description summary or overview
   - Key responsibilities, skills, requirements, machinery skills needed, etc.

3. IMPORTANT:
   - You MUST scroll down to see ALL information on the page
   - Capture the ENTIRE job description text - don't summarize, get every word
   - Some fields might not be present - use empty string "" if not found
   - Extract as much detail as possible
   - Do NOT hallucinate - only extract what you can actually see

=== OUTPUT FORMAT ===

Return a single JSON object with these exact fields:

{{
    "scraped_job_title": "The full job title from the page",
    "recruiter_name": "Company or recruiter name",
    "job_location_text": "Full location text",
    "salary_benefits": "Salary and benefits text (or empty string if not shown)",
    "full_job_description": "THE COMPLETE JOB DESCRIPTION - EVERY SINGLE WORD from the job posting",
    "description_snippet": "Job description/summary text",
    "responsibilities_snippet": "Responsibilities, requirements, skills needed"
}}

CRITICAL:
- Do NOT use write_file or any file operations
- Return valid JSON
- Use "" for missing fields, do NOT hallucinate
- Extract everything you can see on the page

Your ONLY output should be that JSON object!
"""


async def scrape_single_job(
    llm: ChatGoogle,
    job_url: str,
    search_info: Dict[str, str],
    max_steps: int = 50,
) -> Dict[str, Any]:
    """
    Phase 2: Scrape a single job detail page
    Returns dict with job information
    """

    task = _build_job_scrape_task(job_url, search_info)

    agent = Agent(
        task=task,
        llm=llm,
        step_timeout=90,
        max_actions_per_step=8,
        max_failures=3,
    )

    try:
        logger.info(f"Starting scrape for: {job_url}")
        history = await agent.run(max_steps=max_steps)
        logger.info(f"✓ Scrape completed for: {job_url}")
    except Exception as e:
        logger.error(f"Failed to scrape {job_url}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "scraped_job_title": "",
            "recruiter_name": "",
            "job_location_text": "",
            "salary_benefits": "",
            "description_snippet": f"ERROR: {str(e)}",
            "responsibilities_snippet": "",
        }

    # Parse result
    result_json_str = None
    result_json = {}

    # Try structured_output first
    if hasattr(history, "structured_output") and history.structured_output:
        if isinstance(history.structured_output, dict):
            result_json = history.structured_output
        elif isinstance(history.structured_output, str):
            result_json_str = history.structured_output

    # Try final_result()
    if not result_json and result_json_str is None:
        try:
            fr = history.final_result()
            if isinstance(fr, str):
                result_json_str = fr
            elif isinstance(fr, dict):
                result_json = fr
        except Exception:
            pass

    # Parse JSON string if we have one
    if result_json_str:
        try:
            result_json = json.loads(result_json_str)
        except Exception as e:
            logger.error(f"JSON parsing failed for {job_url}: {e}")
            return {
                "scraped_job_title": "",
                "recruiter_name": "",
                "job_location_text": "",
                "salary_benefits": "",
                "description_snippet": f"Parse error: {str(e)}",
                "responsibilities_snippet": "",
            }

    # Extract and clean fields
    cleaned = {
        "job_id": str(uuid.uuid4()),
        "source_url": job_url,
        "search_job_title": search_info.get("job_title", ""),
        "search_location": search_info.get("location", ""),
        "search_radius_miles": search_info.get("miles", ""),
        "scraped_job_title": result_json.get("scraped_job_title", ""),
        "recruiter_name": result_json.get("recruiter_name", ""),
        "job_location_text": result_json.get("job_location_text", ""),
        "salary_benefits": result_json.get("salary_benefits", ""),
        "full_job_description": result_json.get("full_job_description", ""),
        "description_snippet": result_json.get("description_snippet", ""),
        "responsibilities_snippet": result_json.get("responsibilities_snippet", ""),
    }

    return cleaned


async def scrape_jobs_from_links(
    llm: ChatGoogle,
    links: List[Dict[str, Any]],
    search_info: Dict[str, str],
    max_steps_per_job: int = 50,
) -> List[Dict[str, Any]]:
    """
    Phase 2: Scrape all jobs from a list of links
    Returns list of job posting dicts
    """

    logger.info(f"=" * 60)
    logger.info(f"PHASE 2: Scraping {len(links)} job detail pages")
    print(f"\nPHASE 2: Scraping {len(links)} job detail pages")

    all_jobs = []

    for idx, link in enumerate(links, 1):
        job_url = link.get("link_url", "")
        if not job_url:
            continue

        logger.info(f"[{idx}/{len(links)}] Scraping: {job_url}")
        print(f"[{idx}/{len(links)}] Scraping job detail page...")

        try:
            job_data = await scrape_single_job(
                llm=llm,
                job_url=job_url,
                search_info=search_info,
                max_steps=max_steps_per_job
            )
            all_jobs.append(job_data)
            logger.info(f"✓ Scraped: {job_data.get('scraped_job_title', 'N/A')}")
        except Exception as e:
            logger.error(f"Failed to scrape {job_url}: {e}")
            print(f"ERROR scraping job {idx}: {e}")
            continue

    logger.info(f"✓ PHASE 2 Complete: Scraped {len(all_jobs)} jobs")
    print(f"✓ PHASE 2 Complete: Scraped {len(all_jobs)} jobs")

    return all_jobs


def read_links_from_csv(csv_path: str) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Read collected links from CSV file
    Returns: (links, search_info)
    """
    import csv

    links = []
    search_info = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        first_row = None

        for row in reader:
            # Get search info from first row
            if first_row is None:
                first_row = row
                search_info = {
                    "job_title": row.get("search_job_title", ""),
                    "location": row.get("search_location", ""),
                    "miles": row.get("search_radius_miles", "30")
                }

            links.append({
                "page_number": int(row.get("page_number", 1)),
                "link_url": row.get("link_url", ""),
                "link_text": row.get("link_text", ""),
            })

    return links, search_info
