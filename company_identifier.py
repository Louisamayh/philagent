"""
Phase 3: Company Identifier
Uses OpenAI o1 (GPT-5.1) reasoning to identify actual hiring companies from job descriptions
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Set up file logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"company_identification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def extract_clues_from_job(job_description: str, job_title: str, location: str) -> Dict[str, Any]:
    """
    Step 1: Use OpenAI o1 to extract structured clues from job description

    Extracts all 13 clue categories:
    1. Location clues
    2. Sector & industry clues
    3. Product / machinery / technical clues
    4. Software clues
    5. Standards / qualifications clues
    6. Salary / benefits clues
    7. Role / seniority clues
    8. Organisational clues
    9. Narrative / context clues
    10. Work environment / process clues
    11. Customer / market clues
    12. Multi-site & travel clues
    13. Unique differentiators
    """

    logger.info(f"Extracting clues from job: {job_title} in {location}")

    system_prompt = """
You are an expert clue extractor for UK recruiter job adverts.

Your job is to extract EVERY possible clue that could help identify the actual hiring company (not the recruiter).

Extract clues in these 13 categories:

1. **Location Clues**: Primary town, secondary towns (commutable from), region, postcode, nearby industrial clusters, multi-site hints, UK-wide travel mentions

2. **Sector & Industry Clues**: Explicit sector (FMCG, aerospace, automotive, food, LEV, toolmaking), implicit sector, manufacturing type, B2B vs consumer, regulated industry hints (HSG258, ISO standards, WCM)

3. **Product / Machinery / Technical Clues**: Specific machines (CNC brands like Hurco/Fanuc/Mazak, press brakes like Amada/Bystronic, LEV equipment, boilers/HVAC), technical systems (braking & suspension, exhaust after-treatment, metal fabrication, telematics, PLC/SCADA)

4. **Software Clues**: CAD (SolidWorks, AutoCAD, Inventor), CAM (Mastercam, Fusion 360), engineering software (Amtech, Relux), PLC/automation software

5. **Standards / Qualifications Clues**: ISO 9001/14001, WCM, BOHS P601/P602, HSG258, PRINCE2, NEBOSH, COMAH, food safety standards, DVSA/VOSA

6. **Salary / Benefits Clues**: Salary range, bonus structure, healthcare (BUPA), pension type, shift pattern (6-2, 2-12), overtime availability

7. **Role / Seniority Clues**: Job title, reports to, autonomy level, team size, hands-on vs office-based

8. **Organisational Clues**: "Family-run", "household name", "award-winning", "fast-growing SME", "global group", "multi-site", "state-of-the-art facility"

9. **Narrative / Context Clues**: "Complete turnaround", "growth trajectory", "full order book", "significant investment", "working with major OEMs"

10. **Work Environment / Process Clues**: Hazardous environment, fabrication shop, food production, HVAC, cleanroom, foundry/casting, high-voltage, precision machining, heavy lifting

11. **Customer / Market Clues**: Transport/HGV/trailers, exhaust systems, extraction/LEV, CNC toolmaking, building services, FMCG food, aerospace precision

12. **Multi-Site & Travel Clues**: "Covering multiple UK sites", specific site locations, "nationwide surveys", "installation work"

13. **Unique Differentiators**: Any clue that instantly exposes a specific company (e.g., "trailer brake/suspension + telematics" = BPW, "stainless steel exhaust after-treatment" = Eminox)

Return STRICT JSON with these exact fields:

{
  "location_clues": {
    "primary_town": string or null,
    "commute_towns": [string],
    "region": string or null,
    "postcode": string or null,
    "multi_site": boolean
  },
  "sector_clues": {
    "explicit_sectors": [string],
    "implicit_sectors": [string],
    "manufacturing_type": string or null,
    "b2b_or_consumer": string or null
  },
  "machinery_clues": [string],
  "software_clues": [string],
  "standards_clues": [string],
  "salary_benefits_clues": {
    "salary_min": int or null,
    "salary_max": int or null,
    "benefits": [string],
    "shift_pattern": string or null
  },
  "role_clues": {
    "job_title": string,
    "seniority": string or null,
    "reports_to": string or null,
    "team_size": string or null
  },
  "org_clues": [string],
  "narrative_clues": [string],
  "work_environment_clues": [string],
  "customer_market_clues": [string],
  "travel_clues": [string],
  "unique_differentiators": [string],
  "summary_narrative": string
}

Extract EVERY clue you can find. Be thorough!
"""

    user_content = f"""
JOB TITLE: {job_title}
LOCATION: {location}

FULL JOB DESCRIPTION:
{job_description}

Extract ALL clues from this job description that could help identify the actual hiring company.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Using GPT-4
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        clues = json.loads(response.choices[0].message.content)
        logger.info(f"✓ Extracted clues for job: {job_title}")
        return clues

    except Exception as e:
        logger.error(f"Failed to extract clues: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": str(e),
            "location_clues": {},
            "sector_clues": {},
            "machinery_clues": [],
            "software_clues": [],
            "standards_clues": [],
            "salary_benefits_clues": {},
            "role_clues": {},
            "org_clues": [],
            "narrative_clues": [],
            "work_environment_clues": [],
            "customer_market_clues": [],
            "travel_clues": [],
            "unique_differentiators": [],
            "summary_narrative": "Error extracting clues"
        }


def identify_potential_companies(clues: Dict[str, Any], job_title: str, location: str, recruiter_name: str) -> List[Dict[str, Any]]:
    """
    Step 2: Use OpenAI o1 reasoning to identify potential hiring companies

    Returns ranked list of 1-5 potential companies with confidence scores and reasoning
    """

    logger.info(f"Identifying potential companies for: {job_title}")

    system_prompt = f"""
You are an expert in UK industry, manufacturing, and recruitment.

Given extracted clues from a recruiter job advert, identify the ACTUAL HIRING COMPANY (not the recruiter).

CRITICAL RULES:
- The recruiter name is "{recruiter_name}" - NEVER return this as a potential company
- Focus on SPECIFIC, NAMED companies in the UK
- Use the location and clues to narrow down to real companies
- If a clue is very specific (e.g., "only company in Leicester with Hermle 5-axis CNC"), prioritize heavily
- Return 1-5 potential companies ranked by confidence
- Each company must have a confidence score (0.0 to 1.0)
- Provide detailed reasoning for each match

Return STRICT JSON:

{{
  "potential_companies": [
    {{
      "company_name": "Specific Company Name Ltd",
      "confidence": 0.85,
      "reasoning": "Detailed explanation of why this company matches the clues. Reference specific clues like location match, machinery match, sector match, unique differentiators, etc."
    }}
  ],
  "analysis_summary": "Overall analysis of the job and why these companies were selected"
}}

Be specific. Use real company names. Explain your reasoning thoroughly.
"""

    user_content = f"""
JOB TITLE: {job_title}
LOCATION: {location}
RECRUITER (DO NOT RETURN THIS): {recruiter_name}

EXTRACTED CLUES:
{json.dumps(clues, indent=2)}

Based on these clues, identify the most likely actual hiring companies (1-5 ranked by confidence).
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Using GPT-4
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        companies = result.get("potential_companies", [])

        logger.info(f"✓ Identified {len(companies)} potential companies")
        for idx, company in enumerate(companies, 1):
            logger.info(f"  #{idx}: {company.get('company_name', 'N/A')} ({company.get('confidence', 0)*100:.0f}% confidence)")

        return result

    except Exception as e:
        logger.error(f"Failed to identify companies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "potential_companies": [],
            "analysis_summary": f"Error: {str(e)}"
        }


async def enrich_posting_with_company_id(posting: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
    """
    Main function: Takes a job posting and returns enriched data with company identification
    """

    job_id = posting.get("job_id", "UNKNOWN")
    job_title = posting.get("scraped_job_title", "")
    location = posting.get("job_location_text", "")
    recruiter_name = posting.get("recruiter_name", "")
    full_description = posting.get("full_job_description", "")

    logger.info(f"=" * 60)
    logger.info(f"Processing job_id={job_id}: {job_title}")

    # Step 1: Extract clues
    clues = extract_clues_from_job(full_description, job_title, location)

    # Step 2: Identify potential companies
    identification_result = identify_potential_companies(clues, job_title, location, recruiter_name)

    # Build enriched result
    enriched = {
        "job_id": job_id,
        "scraped_job_title": job_title,
        "recruiter_name": recruiter_name,
        "job_location_text": location,
        "full_job_description": full_description,
        "extracted_clues": json.dumps(clues),
        "potential_companies": json.dumps(identification_result.get("potential_companies", [])),
        "analysis_summary": identification_result.get("analysis_summary", ""),
        "top_company": identification_result.get("potential_companies", [{}])[0].get("company_name", "") if identification_result.get("potential_companies") else "",
        "top_confidence": identification_result.get("potential_companies", [{}])[0].get("confidence", 0.0) if identification_result.get("potential_companies") else 0.0,
    }

    logger.info(f"✓ Completed: {enriched.get('top_company', 'No match')} ({enriched.get('top_confidence', 0)*100:.0f}% confidence)")

    return enriched


async def enrich_postings_with_company_identification(postings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process multiple job postings for company identification
    """
    enriched_all: List[Dict[str, Any]] = []

    for posting in postings:
        job_id = posting.get("job_id", "UNKNOWN")
        logger.info(f"🔍 Processing job {job_id}")

        try:
            enriched = await enrich_posting_with_company_id(posting)
            enriched_all.append(enriched)
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
            # Add error entry
            enriched_all.append({
                "job_id": job_id,
                "scraped_job_title": posting.get("scraped_job_title", ""),
                "recruiter_name": posting.get("recruiter_name", ""),
                "job_location_text": posting.get("job_location_text", ""),
                "full_job_description": posting.get("full_job_description", ""),
                "extracted_clues": "{}",
                "potential_companies": "[]",
                "analysis_summary": f"ERROR: {str(e)}",
                "top_company": "",
                "top_confidence": 0.0,
            })

    return enriched_all
