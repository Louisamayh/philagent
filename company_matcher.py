from typing import List, Dict, Any
from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle
import json
import logging
from datetime import datetime
from pathlib import Path

# Set up file logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"company_matching_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnrichedPosting(BaseModel):
    job_id: str = Field(..., description="Matches job_id from jobs_raw")
    scraped_job_title: str
    recruiter_name: str
    job_location_text: str
    description_snippet: str
    responsibilities_snippet: str

    possible_hiring_companies: List[str] = Field(
        ...,
        description="List of 1-5 possible real employers that may have hired the recruiter to fill this role"
    )

    reasoning: str = Field(
        ...,
        description="Short explanation of why these companies are plausible: industry match, location match, role match"
    )


def _build_company_task(posting: Dict[str, Any]) -> str:
    """
    Build instructions for the inference step.
    The agent will:
    - Analyze job description to identify key clues
    - Use web search to find companies matching those clues
    - NOT just repeat the recruiter/agency name
    - Return specific company names
    """

    job_title = posting.get("scraped_job_title", "")
    recruiter = posting.get("recruiter_name", "")
    loc = posting.get("job_location_text", "")
    desc_snip = posting.get("description_snippet", "")
    resp_snip = posting.get("responsibilities_snippet", "")

    return f"""
You are a sourcing/intelligence assistant with web search capabilities. Your job is to identify which actual company (employer)
is hiring for a job that's being advertised by a recruiter/agency.

INPUT:
- job_title: "{job_title}"
- recruiter_name (agency): "{recruiter}"
- job_location_text: "{loc}"
- description_snippet: "{desc_snip}"
- responsibilities_snippet: "{resp_snip}"

YOUR TASK - FOLLOW THESE STEPS:

STEP 1: IDENTIFY CLUES
Carefully analyze the job description and identify specific clues that could help narrow down the hiring company:
- Specific machinery or equipment mentioned (e.g., "Hermle 5-axis CNC", "Fanuc robots", "injection molding")
- Manufacturing processes (e.g., "precision machining", "assembly line", "quality control")
- Industry sector (e.g., aerospace, automotive, food production, pharmaceutical)
- Technologies or software (e.g., "AutoCAD", "SAP", "ISO9001")
- Product types or materials (e.g., "aerospace components", "medical devices", "packaging")
- Certifications or standards (e.g., "AS9100", "ISO 13485")
- Company size indicators (e.g., "multinational", "SME", "family-owned")
- Any other unique details that could identify a specific company

STEP 2: WEB SEARCH
Use web search to find companies in the location that match the clues you identified.
Search strategically:
- "companies in {loc} with [specific machine/process]"
- "[industry] manufacturers in {loc}"
- "[specific technology] companies {loc}"
- Be creative with your searches based on the clues you found

STEP 3: MATCH AND IDENTIFY
- Cross-reference search results with the job requirements
- If there's only ONE company in the area with that specific capability → that's very likely the answer!
- If multiple companies match, rank them by how well they match the specific clues
- Return 1-5 most likely companies

CRITICAL RULES:
- NEVER return the recruiter/agency name ("{recruiter}") as a possible hiring company
- Only return specific company names you found through web search
- DO NOT make up company names - only return companies you actually found
- If a very specific clue (like rare machinery) matches only one company → prioritize that heavily
- Companies MUST be real, specific names (e.g., "Rolls-Royce plc", "Toyota Manufacturing UK")

OUTPUT FORMAT:
Return ONLY a single valid JSON object like this:

{{
  "possible_hiring_companies": [
    "Company 1 Limited",
    "Company 2 plc"
  ],
  "reasoning": "Explain what clues you identified, what you searched for, and why these companies match. Be specific about the key factors (e.g., 'Only company in Leicester with Hermle 5-axis CNC machines')."
}}

Do NOT include any other keys. The reasoning should explain your detective work.
"""


async def _enrich_single_posting(
    llm: ChatGoogle,
    posting: Dict[str, Any],
    max_steps: int,
) -> Dict[str, Any]:
    """
    Uses browser_use.Agent to infer possible hiring companies.
    Returns a dict shaped for EnrichedPosting.
    """

    task = _build_company_task(posting)

    agent = Agent(
        task=task,
        llm=llm,
        step_timeout=120,  # Increased for web search
        max_actions_per_step=10,  # Allow more actions for searching
        max_failures=3,
        # We'll parse JSON manually again
    )

    job_id = posting.get("job_id", "UNKNOWN")
    job_title = posting.get("scraped_job_title", "")
    logger.info(f"Starting company matching for job_id={job_id}: {job_title}")

    try:
        history = await agent.run(max_steps=max_steps)
        logger.info(f"✓ Company matching completed for job_id={job_id}")
    except Exception as e:
        logger.error(f"Failed to match companies for job_id={job_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty result
        return {
            "job_id": job_id,
            "scraped_job_title": job_title,
            "recruiter_name": posting.get("recruiter_name", ""),
            "job_location_text": posting.get("job_location_text", ""),
            "description_snippet": posting.get("description_snippet", ""),
            "responsibilities_snippet": posting.get("responsibilities_snippet", ""),
            "possible_hiring_companies": [],
            "reasoning": f"ERROR: {str(e)}"
        }

    # We'll grab final_result() as text and json.loads it
    final_txt = ""
    if hasattr(history, "structured_output") and history.structured_output:
        if isinstance(history.structured_output, str):
            final_txt = history.structured_output
        else:
            try:
                final_txt = json.dumps(history.structured_output)
            except Exception:
                final_txt = ""
    if not final_txt:
        try:
            fr = history.final_result()
        except Exception:
            fr = None
        if isinstance(fr, str):
            final_txt = fr

    possible_companies: List[str] = []
    reasoning: str = ""

    if final_txt:
        try:
            data = json.loads(final_txt)
            pc = data.get("possible_hiring_companies", [])
            if isinstance(pc, list):
                possible_companies = [c for c in pc if isinstance(c, str)]
            rsn = data.get("reasoning", "")
            if isinstance(rsn, str):
                reasoning = rsn
        except Exception as e:
            reasoning = f"Parser error, raw text: {final_txt[:200]}... ({e})"

    # Fallback safeguards
    if not possible_companies:
        possible_companies = []
        if not reasoning:
            reasoning = "No clear match, could not infer hiring company."

    enriched = EnrichedPosting(
        job_id=posting["job_id"],
        scraped_job_title=posting.get("scraped_job_title", ""),
        recruiter_name=posting.get("recruiter_name", ""),
        job_location_text=posting.get("job_location_text", ""),
        description_snippet=posting.get("description_snippet", ""),
        responsibilities_snippet=posting.get("responsibilities_snippet", ""),
        possible_hiring_companies=possible_companies[:5],
        reasoning=reasoning.strip(),
    )

    return enriched.model_dump()


async def enrich_postings_with_companies(
    llm: ChatGoogle,
    postings: List[Dict[str, Any]],
    max_steps: int = 50,  # Increased for web search operations
) -> List[Dict[str, Any]]:
    """
    Loop over every scraped posting and infer possible hiring companies.
    Returns list of dicts with fields from EnrichedPosting.
    """
    enriched_all: List[Dict[str, Any]] = []
    for p in postings:
        job_id = p.get("job_id", "UNKNOWN")
        print(f"🔍 Inferring employer for job_id={job_id} ({p.get('scraped_job_title','')}) ...")
        enriched = await _enrich_single_posting(llm, p, max_steps=max_steps)
        enriched_all.append(enriched)
    return enriched_all
