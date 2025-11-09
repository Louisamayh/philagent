from typing import List, Dict, Any
from pydantic import BaseModel, Field
from browser_use import Agent, ChatGoogle
import json


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
    - NOT just repeat the recruiter/agency name
    - Suggest real employers
    """

    job_title = posting.get("scraped_job_title", "")
    recruiter = posting.get("recruiter_name", "")
    loc = posting.get("job_location_text", "")
    desc_snip = posting.get("description_snippet", "")
    resp_snip = posting.get("responsibilities_snippet", "")

    return f"""
You are a sourcing/intelligence assistant. Your job is to infer which actual company (employer)
might be hiring for a given job advert that is currently being run by a recruiter / agency.

INPUT:
- job_title: "{job_title}"
- recruiter_name (agency): "{recruiter}"
- job_location_text: "{loc}"
- description_snippet: "{desc_snip}"
- responsibilities_snippet: "{resp_snip}"

TASK:
1. You MUST ignore the recruiter/agency name. That is NOT the hiring company.
2. Based on:
   - Industry keywords in job_title and responsibilities_snippet
   - Tech / domain keywords (e.g. aerospace, automotive, food production, precision engineering)
   - Seniority level
   - job_location_text (town / region / area)
   infer 1 to 5 plausible real hiring companies that could be using that recruiter.

3. Think like a headhunter:
   - Which local companies in that area plausibly hire for this exact role?
   - Which companies match the product / process mentioned? (e.g. “Tier 1 automotive”, “CNC precision machining”, “FMCG food packaging line maintenance”)
   - It is okay to include subsidiaries or well-known local plants/factories.

4. VERY IMPORTANT:
   - NEVER return the recruiter/agency name as a possible hiring company.
   - Only return plausible end-employers.
   - Companies MUST be specific names, not generic strings like "an aerospace firm".
   - If you're not sure of exact names, produce the most likely named companies operating in that geography + domain.
   - Between 1 and 5 companies is fine.

OUTPUT FORMAT:
Return ONLY a single valid JSON object like this:

{{
  "possible_hiring_companies": [
    "Company 1 Limited",
    "Company 2 plc"
  ],
  "reasoning": "Short explanation using location, industry and responsibilities."
}}

Do NOT include any other keys. The reasoning should be concise but concrete.
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
        step_timeout=90,
        max_actions_per_step=6,
        max_failures=2,
        # We'll parse JSON manually again
    )

    history = await agent.run(max_steps=max_steps)

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
    max_steps: int = 20,
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
