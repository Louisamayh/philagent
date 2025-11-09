import uuid
from typing import List
from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle


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
You are a data collection browser agent. You MUST follow these rules exactly:

GOAL:
1. Go to this URL: {base_url}
2. On the page:
   - Enter the job title: "{job_title}"
   - Enter the location: "{location}"
   - Enter the radius/miles: "{miles}" (miles radius)
   - Start the search.

3. After the search results load:
   - Stay on that first results page only.
   - Do NOT click in to any individual job page.
   - Do NOT paginate to page 2.
   - Do NOT follow recruiter links.

4. For EVERY job card visible in the results list on that single page (if ~25 jobs appear, do all ~25):
   Collect the following, using empty string if missing:
   - scraped_job_title: The job title text shown.
   - recruiter_name: The 'posted by' / agency / recruiter name shown.
   - job_location_text: The job location shown (e.g. 'Leicester, Leicestershire').
   - salary_benefits: Any salary/benefits info visible on that card (e.g. '£45k + car + bonus').
   - description_snippet: The short pitch/summary paragraph visible on the card.
   - responsibilities_snippet: Any bullet points or listed duties/responsibilities visible on the card.

Make sure you capture recruiter_name even if it's clearly an agency (e.g. 'ABC Recruitment Ltd').
We are NOT trying to infer the real hiring company in this step. Just scrape what you can see.

5. Return your final answer as a JSON list of objects.
Each object MUST include:
   - job_id: a freshly generated UUID for that posting (UUID4 format).
   - source_url: the URL you were on when scraping results (after search).
   - search_job_title: "{job_title}"
   - search_location: "{location}"
   - search_radius_miles: "{miles}"
   - scraped_job_title
   - recruiter_name
   - job_location_text
   - salary_benefits
   - description_snippet
   - responsibilities_snippet

6. IMPORTANT:
   - Do NOT include pagination info.
   - Do NOT include ads/sponsored widgets unless they are real job cards.
   - Do NOT hallucinate fields you cannot see. Use "" if missing.
   - Make sure the JSON you return is valid and parseable.

Your ONLY output should be that JSON list of job posting objects.
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
        max_failures=2,
        # We are NOT passing output_model_schema here because we want list[...] not single obj.
    )

    history = await agent.run(max_steps=max_steps)

    # browser_use Agent returns 'final_result()' as text OR 'structured_output'
    # We'll try both.
    result_json_str = None

    # try structured_output first
    if hasattr(history, "structured_output") and history.structured_output:
        # structured_output might already be a python object (list[dict]) or a string
        if isinstance(history.structured_output, list):
            result_json = history.structured_output
        elif isinstance(history.structured_output, str):
            result_json_str = history.structured_output
        else:
            # fallback to final_result call
            result_json_str = None
    else:
        # try final_result()
        try:
            fr = history.final_result()
        except Exception:
            fr = None

        if isinstance(fr, str):
            result_json_str = fr
        else:
            # last ditch, just give up gracefully
            result_json_str = None

    if result_json_str is not None:
        import json
        try:
            result_json = json.loads(result_json_str)
        except Exception as e:
            print(f"WARNING: couldn't json.loads agent result: {e}")
            result_json = []

    # result_json should now be a python list of dicts
    if not isinstance(result_json, list):
        print("WARNING: agent did not return a list. Returning empty.")
        return []

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

    return cleaned
