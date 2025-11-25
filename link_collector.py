"""
Phase 1: Link Collection Agent
Collects job detail page URLs from CV-Library search results (maximum 5 pages)
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
log_file = LOG_DIR / f"link_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _read_extracted_content_files(page_number: int, current_page_url: str) -> Dict[str, Any]:
    """
    Fallback: Read links from extracted_content_*.md files that agent created
    These files contain markdown tables with job links
    """
    import re
    from pathlib import Path

    all_links = []

    # Try to find and read extracted_content files
    for i in range(10):  # Check up to 10 files
        file_path = Path(f"extracted_content_{i}.md")
        if not file_path.exists():
            break  # No more files

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract URL from content (looks for cv-library.co.uk/job/ links)
            # Pattern matches both full URLs and relative paths
            url_pattern = r'(?:https?://www\.cv-library\.co\.uk)?(/job/[\d]+/[^\s\|\)]+)'
            matches = re.findall(url_pattern, content)

            for match in matches:
                # Convert relative path to full URL if needed
                if match.startswith('/job/'):
                    full_url = f"https://www.cv-library.co.uk{match}"
                else:
                    full_url = match

                # Extract job title from the line (it's usually before the URL in markdown table)
                # Pattern: | Job Title | URL |
                title_match = re.search(rf'\|\s*([^|]+?)\s*\|\s*{re.escape(match)}', content)
                title = title_match.group(1).strip() if title_match else "Unknown Title"

                all_links.append({
                    "page_number": page_number,
                    "link_url": full_url,
                    "link_text": title
                })
        except Exception as e:
            logger.debug(f"Could not read {file_path}: {e}")
            continue

    return {
        "current_page_url": current_page_url,
        "links": all_links
    }


def _build_link_collection_task(base_url: str, job_title: str, location: str, miles: str, page_number: int, search_url: str = None) -> str:
    """
    Instructions for Phase 1: Collect job detail page links from ONE specific page
    """

    if page_number == 1:
        navigation_instructions = f"""
1. Go to this URL: {base_url}

2. Enter the search criteria:
   - Job title: "{job_title}"
   - Location: "{location}"
   - Miles/radius: "{miles}" miles
   - Start the search

3. You should now be on PAGE 1 of the job posting search results."""
    else:
        navigation_instructions = f"""
1. Go directly to this search results URL: {search_url}

2. You should be on page {page_number - 1} of the search results.

3. Click the pagination button for page {page_number} (look for the number "{page_number}" button at the bottom of the page).

4. You should now be on PAGE {page_number} of the search results."""

    return f"""
You are a link collection agent. Your ONLY job is to collect the top 5 job posting URLs from CV-Library search results.

=== YOUR TASK ===

Collect job detail page URLs from PAGE {page_number} ONLY.

=== CRITICAL INSTRUCTIONS FOR LINK COLLECTION ===

UNDERSTANDING THE PAGE LAYOUT:
- Job listings are displayed as VERTICAL CARDS stacked one on top of another
- Each card represents one job posting
- At the TOP of each card is a JOB TITLE which is a clickable link
- The link embedded in the job title text goes to the full job description page
- You MUST extract the href/URL from each job title link, start at the top and work your way down one at a time. 

STEPS:

{navigation_instructions}

4. VERIFY YOU'RE ON THE CORRECT PAGE:
   - Check the URL or page indicator to confirm you're on PAGE {page_number}
   - If not on the correct page, navigate there first
   - Do NOT proceed until you're on the right page

5. CHECK IF THIS PAGE EXISTS:
   - Look for job results on the page
   - Check for messages like "X-Y of Z total" to understand how many jobs exist
   - If the page shows "0 jobs" or "no results", this page doesn't exist - return empty links immediately
   - If you see job results, proceed with collection

6. COLLECT ALL LINKS FROM THIS PAGE:
   - Scroll down to the BOTTOM of the page first to load all content
   - Typically 20-25 job cards per page (but last pages may have fewer)
   - Start from the TOP card
   - For EACH job card (working DOWN the page):
     * Locate the job title at the top of the card
     * The job title is a clickable link - extract its URL/href
     * Example URL format: "https://www.cv-library.co.uk/job/12345678/job-title-here"
     * Add this URL to your collection list
   - Collect EVERY job card visible on the page

6. CAPTURE THE CURRENT PAGE URL:
   - After collecting all links, note the current page URL
   - We'll need this URL to navigate to the next page

7. CRITICAL REQUIREMENTS:
   - You MUST have AT LEAST 15 links before returning (unless it's the last page with fewer jobs)
   - Do NOT call done() until you have collected ALL links visible on the page
   - Do NOT visit the job detail pages yet
   - Do NOT scrape job information yet
   - Do NOT navigate to other pages

=== OUTPUT FORMAT ===

⚠️ CRITICAL: When you call done(), you MUST pass the actual JSON object with all the links as the 'text' parameter.
DO NOT just say "the results are provided" - you must ACTUALLY provide the full JSON in the done() call.

The JSON object must have:
   - current_page_url: The URL of the current search results page (string)
   - links: List of ALL link objects you collected

Each link object MUST have:
   - link_url: The full URL of the job detail page
   - link_text: The job title text from the link (for verification)

Example done() call:
done(text='{{ "current_page_url": "https://www.cv-library.co.uk/...", "links": [{{ "link_url": "https://www.cv-library.co.uk/job/12345678/...", "link_text": "Senior Software Engineer" }}, {{ "link_url": "https://www.cv-library.co.uk/job/87654321/...", "link_text": "Junior Developer" }}] }}', success=True)

Example output format:
{{
    "current_page_url": "https://www.cv-library.co.uk/search-jobs?q=engineer&geo=london&distance=10&page={page_number}",
    "links": [
        {{
            "link_url": "https://www.cv-library.co.uk/job/12345678/software-engineer",
            "link_text": "Senior Software Engineer"
        }},
        {{
            "link_url": "https://www.cv-library.co.uk/job/87654321/data-analyst",
            "link_text": "Data Analyst - London"
        }}
    ]
}}

CRITICAL RULES - READ CAREFULLY:
- If the page shows 0 jobs or "no results", return empty links immediately: {{"current_page_url": "...", "links": []}}
- Otherwise, collect ALL job cards visible on the page
- Pages typically have 15-25 links (but last pages may have fewer - that's okay!)
- Do NOT use write_file or any file operations
- Keep ALL links in memory
- Return as valid JSON with ALL collected links
- Do NOT visit the job detail pages yet
- ONLY collect from PAGE {page_number}
- Collect EVERY job card visible - don't stop until you've scrolled through the entire page

BEFORE YOU CALL DONE:
- Did you scroll through the ENTIRE page?
- Did you extract EVERY job card you saw?
- If page is empty/no results, return empty links
- If page has jobs, return ALL of them (even if fewer than 15)

Your ONLY output should be that JSON object with ALL links!
"""


async def collect_links_from_single_page(
    llm: ChatGoogle,
    base_url: str,
    job_title: str,
    location: str,
    miles: str,
    page_number: int,
    search_url: str = None,
    max_steps: int = 150,
) -> Dict[str, Any]:
    """
    Phase 1: Collect job detail page links from ONE specific page
    Returns dict with: current_page_url (str), links (list)
    """

    task = _build_link_collection_task(base_url, job_title, location, miles, page_number, search_url)

    agent = Agent(
        task=task,
        llm=llm,
        step_timeout=120,
        max_actions_per_step=10,
        max_failures=5,
    )

    logger.info(f"Collecting links from page {page_number} for '{job_title}' in '{location}'")
    print(f"📄 Page {page_number}: Collecting links...")

    try:
        history = await agent.run(max_steps=max_steps)
        steps_used = len(history.history) if hasattr(history, 'history') else 'unknown'
        logger.info(f"Page {page_number} collection completed. Steps: {steps_used}/{max_steps}")

        # Warn if we hit max_steps (agent might have been cut off mid-task)
        if steps_used == max_steps or steps_used == 'unknown':
            logger.warning(f"⚠ Page {page_number} may have hit max_steps limit ({max_steps})")
            logger.warning(f"⚠ Agent might not have finished collecting all links")
            print(f"⚠ WARNING: Page {page_number} used all {max_steps} steps - may be incomplete!")
    except Exception as e:
        logger.error(f"Page {page_number} collection failed: {e}")
        print(f"ERROR: Page {page_number} failed: {e}")
        import traceback
        traceback.print_exc()
        return {"current_page_url": "", "links": []}

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
        except Exception as e:
            logger.debug(f"final_result() raised: {e}")

    # ADDITIONAL FALLBACK: Check agent's extracted_content (might be in history)
    if not result_json and result_json_str is None:
        try:
            # Look through agent's action history for extracted content
            if hasattr(history, 'history') and history.history:
                for action in reversed(history.history):  # Start from most recent
                    if hasattr(action, 'result') and action.result:
                        result_text = str(action.result)
                        # Look for JSON pattern in the result
                        if '"link_url"' in result_text and '"link_text"' in result_text:
                            # Try to extract JSON from the text
                            import re
                            json_match = re.search(r'\{[\s\S]*"links"[\s\S]*\[[\s\S]*\][\s\S]*\}', result_text)
                            if json_match:
                                try:
                                    result_json = json.loads(json_match.group(0))
                                    logger.info("✓ Found links in agent's action history!")
                                    break
                                except:
                                    pass
        except Exception as e:
            logger.debug(f"Could not extract from agent history: {e}")

    # Parse JSON string if we have one
    if result_json_str:
        try:
            result_json = json.loads(result_json_str)
        except Exception as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw string (first 1000 chars): {result_json_str[:1000]}")

            # FALLBACK: Try to read extracted_content files that agent created
            logger.info("Attempting fallback: reading extracted_content files...")
            fallback_links = _read_extracted_content_files(page_number, search_url or "")
            if fallback_links["links"]:
                logger.info(f"✓ Fallback successful! Found {len(fallback_links['links'])} links from extracted_content files")
                return fallback_links

            return {"current_page_url": "", "links": []}

    # Validate result is a dict with required fields
    if not isinstance(result_json, dict):
        logger.error(f"Agent did not return a dict. Got type: {type(result_json)}")
        return {"current_page_url": "", "links": []}

    # Extract data
    current_page_url = result_json.get("current_page_url", search_url or "")
    links_list = result_json.get("links", [])

    # Clean and validate links
    cleaned_links = []
    for item in links_list:
        if isinstance(item, dict) and "link_url" in item:
            cleaned_links.append({
                "page_number": page_number,
                "link_url": item.get("link_url", ""),
                "link_text": item.get("link_text", ""),
            })

    logger.info(f"✓ Page {page_number}: Collected {len(cleaned_links)} links")
    print(f"✓ Page {page_number}: Collected {len(cleaned_links)} links")

    # Warn if we got very few links (might indicate incomplete collection)
    if len(cleaned_links) < 10 and page_number <= 3:
        logger.warning(f"⚠ Page {page_number} only collected {len(cleaned_links)} links (expected ~25)")
        logger.warning(f"⚠ This might indicate the agent stopped mid-task")

    return {
        "current_page_url": current_page_url,
        "links": cleaned_links
    }


def save_links_to_csv(links: List[Dict[str, Any]], output_path: str, search_info: Dict[str, str], append: bool = False):
    """
    Save collected links to CSV file
    If append=True, appends to existing file (for page-by-page saves)
    If append=False, creates new file with header
    """
    import csv

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "link_id",
        "page_number",
        "link_url",
        "link_text",
        "search_job_title",
        "search_location",
        "search_radius_miles",
        "collected_at"
    ]

    # Determine mode and whether to write header
    mode = 'a' if append else 'w'
    write_header = not append

    with open(output_path, mode, encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        for link in links:
            writer.writerow({
                "link_id": str(uuid.uuid4()),
                "page_number": link.get("page_number", 1),
                "link_url": link.get("link_url", ""),
                "link_text": link.get("link_text", ""),
                "search_job_title": search_info.get("job_title", ""),
                "search_location": search_info.get("location", ""),
                "search_radius_miles": search_info.get("miles", ""),
                "collected_at": datetime.now().isoformat(),
            })

    action = "Appended" if append else "Saved"
    print(f"✓ {action} {len(links)} links to {output_path}")
    logger.info(f"{action} {len(links)} links to {output_path}")
