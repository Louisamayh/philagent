"""
Phase 3: Company Identifier
Uses OpenAI GPT-4o reasoning to identify actual hiring companies from job descriptions
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
    Step 1: Use OpenAI GPT-4o to extract structured clues from job description

    Extracts all 13 clue categories:
    1. Location Address/Postcode - the company has to exist within the area of the postcode/address provided
    2. Purpose of the company - what they make/do
    3. Product / machinery / technical clues 
    4. Sector & industry clues
    6. Specific machinery or equipment mentioned (e.g., "Hermle 5-axis CNC", "Fanuc robots", "injection molding") - could the company have that equipment?
    7. Standards / qualifications clues - could the company hire that specific role?
    8. Salary / benefits clues
    9. Role / seniority clues - could the company hire that specific role? What kind of company can hire that role?
    10. Organisational clues
    11. Narrative / context clues
    12. Work environment / process clues
    13. Customer / market clues
    14. Multi-site & travel clues
    15. Unique differentiators
    """

    logger.info(f"Extracting clues from job: {job_title} in {location}")

    system_prompt = """
You are an expert clue extractor for UK recruiter job adverts.

Your job is to extract EVERY possible clue that could help identify the actual hiring company (not the recruiter).

Extract clues in these 13 categories:

1. **Location Clues**: Primary town, secondary towns (commutable from), region, postcode, nearby industrial clusters, multi-site hints, UK-wide travel mentions

2. **Sector & Industry Clues**: Purpose of the company and explicit sector (FMCG, aerospace, automotive, food, LEV, toolmaking), implicit sector, manufacturing type, B2B vs consumer, regulated industry hints (HSG258, ISO standards, WCM)

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
            model="gpt-4o",  # Using GPT-4o (supports JSON mode)
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


def identify_potential_companies(clues: Dict[str, Any], job_title: str, location: str, recruiter_name: str, postcode: str = "") -> List[Dict[str, Any]]:
    """
    Step 2: Use OpenAI GPT-4o reasoning to identify potential hiring companies

    Returns ranked list of 1-5 potential companies with confidence scores and reasoning
    """

    logger.info(f"Identifying potential companies for: {job_title}")

    system_prompt = f"""
You are an expert in UK industrial geography, manufacturing, and recruitment. You identify hiring companies using a STRUCTURED, TRANSPARENT process.

The recruiter is "{recruiter_name}" - NEVER suggest them as the hiring company.

🎯 REQUIRED PROCESS (Show Your Work):

STEP 1: WEB SEARCH
Use live web search to find companies in the location that match the clues you identified. The company must be PHYSICALLY LOCATED in "{location}"'s postcode or the immediate surrounding area mentioned in the location clues.

Search strategically:
- "companies in {postcode} with [specific machine/process]"
- "[industry] in {postcode}"
- "[specific technology] companies {postcode}"
- "[company type] in {postcode} (e.g., "aerospace manufacturers in Leicester")
- Be creative with your searches based on the clues you found

**GOALS IDENTIFY COMPANIES IN THE AREA**

**STEP 2: LIST POTENTIAL COMPANIES**
Identify 3-5 real companies that are:
- Addresses are in the specified area (NOT just "have presence in UK")
- Operate in the relevant sectors from Step 1
- Match the size/type suggested by clues (SME vs corporate, family-owned, etc.)

**STEP 3: VERIFY COMPANY POSTCODES**
For EACH company, you MUST verify their actual registered postcode by searching:
- Search query: "[Company Name] gov.uk postcode"
- Check Companies House or government records
- Extract their registered postcode

**STEP 4: SCORE EACH COMPANY (0-10 points each)**
For each company, score on these criteria:

| Criterion | Points (0-10) | Notes |
|-----------|---------------|-------|
| Geography match (POSTCODE) | /10 | **10 points ONLY if company postcode EXACTLY matches job postcode. 0 points if different.** Use "Company Name gov.uk postcode" to verify. |
| Sector/industry match | /10 | Right manufacturing type? |
| Multi-site match (if applicable) | /10 | Has multiple sites mentioned? |
| Machinery/technical match | /10 | Uses mentioned equipment/software? |
| Company narrative match | /10 | "Turnaround", "family-owned", "growth" etc.? |
| Salary realism | /10 | Salary fits company size/type? |
| **TOTAL** | **/60** | Sum all scores |

🚨 CRITICAL: If job postcode is "{postcode}" and company postcode is different, geography score = 0 and exclude company entirely.

**STEP 5: RANK BY TOTAL SCORE**
- Rank companies by total score (highest first)
- Convert to confidence: Score/60 → 0.0-1.0 confidence
- Return top 3-5 companies with matching postcodes only

**CRITICAL RULES:**
- Location match is MANDATORY (0 points = exclude completely)
- Show scoring breakdown in reasoning
- If unsure about location, score 0 and exclude
- Better to return 1 good match than 5 wrong locations

Return STRICT JSON:

{{
  "industrial_cluster": {{
    "location": "Specific town/area from clues",
    "main_sectors": ["Sector 1", "Sector 2", "Sector 3"]
  }},
  "potential_companies": [
    {{
      "company_name": "Specific Company Name Ltd",
      "company_postcode": "LE8 6LP",
      "postcode_matches_job": true,
      "location_verified": "Town name where company is based",
      "confidence": 0.85,
      "total_score": 51,
      "score_breakdown": {{
        "geography": 10,
        "sector": 9,
        "multi_site": 8,
        "machinery": 9,
        "narrative": 8,
        "salary": 7
      }},
      "reasoning": "MUST START: 'Company postcode: [postcode] - matches job postcode [{postcode}]. Located in [location].' Then explain other matches."
    }}
  ],
  "analysis_summary": "Overall process summary"
}}
"""

    user_content = f"""
JOB TITLE: {job_title}
LOCATION: {location}
POSTCODE: {postcode}
RECRUITER (DO NOT RETURN THIS): {recruiter_name}

EXTRACTED CLUES:
{json.dumps(clues, indent=2)}

🎯 CRITICAL REQUIREMENTS:

1. **POSTCODE VERIFICATION IS MANDATORY**:
   - Job postcode: "{postcode}"
   - For EACH company, search "[Company Name] gov.uk postcode" to verify their registered postcode
   - ONLY suggest companies with EXACT postcode match: "{postcode}"
   - If company has different postcode → Geography score = 0 → EXCLUDE entirely

2. **If no postcode provided**:
   - Only suggest companies physically located in "{location}"
   - Verify location through Companies House / gov.uk records

3. **DO NOT suggest**:
   - Companies from other postcodes/areas even if sector matches perfectly
   - National companies unless they have facility in THIS postcode

4. **Searching**: keep searching until you find companies that meet the postcode/location requirement

Based on these clues, identify the most likely actual hiring companies (1-5 ranked by confidence) with VERIFIED MATCHING POSTCODES.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4o (supports JSON mode)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        companies = result.get("potential_companies", [])
        cluster = result.get("industrial_cluster", {})

        logger.info(f"✓ Industrial Cluster: {cluster.get('location', 'N/A')} → {', '.join(cluster.get('main_sectors', []))}")
        logger.info(f"✓ Identified {len(companies)} potential companies")
        for idx, company in enumerate(companies, 1):
            score = company.get('total_score', 0)
            confidence = company.get('confidence', 0)
            company_postcode = company.get('company_postcode', 'N/A')
            postcode_match = company.get('postcode_matches_job', False)
            match_symbol = "✓" if postcode_match else "✗"
            logger.info(f"  #{idx}: {company.get('company_name', 'N/A')} | Postcode: {company_postcode} {match_symbol} | Score: {score}/60 ({confidence*100:.0f}%)")

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

    # Extract postcode from location clues
    postcode = ""
    if clues and "location_clues" in clues:
        postcode = clues["location_clues"].get("postcode", "") or ""

    # Step 2: Identify potential companies
    identification_result = identify_potential_companies(clues, job_title, location, recruiter_name, postcode)

    # Build enriched result
    potential_companies = identification_result.get("potential_companies", [])
    industrial_cluster = identification_result.get("industrial_cluster", {})

    # Create readable company list for CSV
    all_companies_readable = ""
    if potential_companies:
        company_strings = [
            f"{company.get('company_name', 'N/A')} ({company.get('confidence', 0)*100:.0f}%, Score: {company.get('total_score', 0)}/60)"
            for company in potential_companies
        ]
        all_companies_readable = " | ".join(company_strings)

    # Create industrial cluster summary
    cluster_summary = ""
    if industrial_cluster:
        location = industrial_cluster.get('location', 'N/A')
        sectors = ', '.join(industrial_cluster.get('main_sectors', []))
        cluster_summary = f"{location}: {sectors}"

    enriched = {
        "job_id": job_id,
        "scraped_job_title": job_title,
        "recruiter_name": recruiter_name,
        "job_location_text": location,
        "full_job_description": full_description,
        "extracted_clues": json.dumps(clues),
        "industrial_cluster": json.dumps(industrial_cluster),
        "cluster_summary": cluster_summary,
        "potential_companies": json.dumps(potential_companies),
        "all_companies_readable": all_companies_readable,
        "analysis_summary": identification_result.get("analysis_summary", ""),
        "top_company": potential_companies[0].get("company_name", "") if potential_companies else "",
        "top_confidence": potential_companies[0].get("confidence", 0.0) if potential_companies else 0.0,
        "top_score": potential_companies[0].get("total_score", 0) if potential_companies else 0,
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
                "industrial_cluster": "{}",
                "cluster_summary": "",
                "potential_companies": "[]",
                "all_companies_readable": "",
                "analysis_summary": f"ERROR: {str(e)}",
                "top_company": "",
                "top_confidence": 0.0,
                "top_score": 0,
            })

    return enriched_all
