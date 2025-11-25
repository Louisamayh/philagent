import os
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

# Load environment variables
load_dotenv()

# Initialize Tavily client for web search
tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Set up file logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"company_identification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ======================================================
# 0) DYNAMIC INDUSTRY EXAMPLES (Reference Only)
# ======================================================
# The system now dynamically infers industries from job content.


# ======================================================
# 1) DYNAMIC SEARCH TERM EXTRACTION
# ======================================================
def extract_dynamic_search_terms(job_description: str, job_title: str, clues: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses GPT to extract industry-specific search terms dynamically from the job description.
    This replaces hardcoded lists and works for ANY industry.
    """

    prompt = f"""
You are extracting search terms from a job description to help identify the hiring company.

Analyze this job and extract industry-specific terms that would help find companies in this field.

Extract:
1. **Key Technologies/Tools**: Brand names, software, equipment, systems (e.g., "Mazak CNC", "Salesforce", "React", "AWS")
2. **Industry-Specific Terms**: Technical processes, methodologies, standards (e.g., "CNC milling", "agile development", "RIBA standards")
3. **Certifications/Standards**: Required qualifications, compliance standards (e.g., "ISO 9001", "FCA regulated", "HSG258", "AWS Certified")
4. **Company Characteristics**: What kind of company would hire this role? (e.g., "manufacturing", "consultancy", "fintech", "SaaS")

Return STRICT JSON:
{{
  "key_technologies": ["term1", "term2", ...],
  "industry_terms": ["term1", "term2", ...],
  "certifications_standards": ["term1", "term2", ...],
  "company_type_hints": ["hint1", "hint2", ...],
  "search_keywords": ["keyword1", "keyword2", ...] // Top 5-8 most distinctive search terms
}}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:2000]}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        dynamic_terms = json.loads(response.choices[0].message.content)

        # Merge dynamic terms into clues
        machinery_clues = clues.get("machinery_clues", [])
        if not isinstance(machinery_clues, list):
            machinery_clues = []

        software_clues = clues.get("software_clues", [])
        if not isinstance(software_clues, list):
            software_clues = []

        # Add dynamically extracted terms
        for tech in dynamic_terms.get("key_technologies", []):
            if tech and tech not in machinery_clues:
                machinery_clues.append(tech)

        for term in dynamic_terms.get("industry_terms", []):
            if term and term not in machinery_clues:
                machinery_clues.append(term)

        clues["machinery_clues"] = machinery_clues
        clues["software_clues"] = software_clues
        clues["dynamic_search_terms"] = dynamic_terms

        # Store search keywords for later use
        clues["search_keywords"] = dynamic_terms.get("search_keywords", [])

        logger.info(f"✓ Extracted {len(dynamic_terms.get('search_keywords', []))} dynamic search keywords")
        return clues

    except Exception as e:
        logger.error(f"Failed to extract dynamic search terms: {e}")
        # Return clues unchanged if extraction fails
        clues["dynamic_search_terms"] = {}
        clues["search_keywords"] = []
        return clues


# ======================================================
# 2) INDUSTRY INFERENCE (PRIMARY + 2 ALTERNATES)
# ======================================================
def infer_industry_candidates_with_gpt(clues: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """
    Returns:
    {
      "primary": str,
      "alternates": [str, str],
      "created_new": bool,
      "new_label": str or null
    }
    """
    deterministic_hint = None
    explicit_sectors = []

    if isinstance(clues.get("sector_clues"), dict):
        deterministic_hint = clues["sector_clues"].get("manufacturing_type")
        explicit_sectors = clues["sector_clues"].get("explicit_sectors") or []

    prompt = f"""
You are classifying a UK recruiter advert into ONE main industry + TWO plausible alternates.

⚠️ CRITICAL DISTINCTIONS:

1. MANUFACTURER vs. SERVICE/CONTRACTOR vs. SOFTWARE/TECH:
   - Does the company MAKE physical products? → Manufacturing (e.g., "CNC milling", "food production", "automotive parts")
   - Does the company INSTALL/MAINTAIN systems? → Services/contractor (e.g., "industrial installation", "field service")
   - Does the company DESIGN systems/buildings? → Consultancy/design (e.g., "MEP design", "architectural services")
   - Does the company build SOFTWARE/digital products? → Tech (e.g., "SaaS platform", "mobile app development", "cloud infrastructure")
   - Does the company provide professional services? → Professional services (e.g., "financial services", "legal services", "consulting")

2. SPECIALIST vs. GENERALIST ROLES:
   - CNC Miller, React Developer, Financial Analyst, Panel Wirer → SPECIALIST (specific industry)
   - General Operative, Site Labourer, Installer, Office Admin → GENERALIST (service contractor or broad support)

3. PRIMARY DUTY CHECK (most important):
   - "operating CNC mill" → Company makes things (CNC milling manufacturer)
   - "developing React applications" → Company builds software (web development)
   - "moving and installing machinery" → Company installs things (industrial services)
   - "analyzing financial data" → Company provides services (financial services/fintech)
   - "designing buildings" → Company designs things (architectural consultancy)

4. CONTEXT CLUES:
   - "UK-wide travel" + "customer sites" = Field service/contractor
   - "Workshop-based" + "manufacturing" = Manufacturer
   - "Remote work" + "agile sprints" + "Git" = Software/tech company
   - "City office" + "FCA regulated" = Financial services
   - "Design office" + "RIBA standards" = Architecture/design consultancy

5. BE SPECIFIC BUT REALISTIC:
   - Describe the industry precisely based on what the company does
   - Use common industry terminology (e.g., "fintech", "SaaS", "precision engineering", "food manufacturing")
   - Avoid generic terms like "engineering" or "technology" - be specific
   - If manufacturing, specify what type (e.g., "CNC machining", not just "manufacturing")

🎯 PROCESS:
1. Read job title + primary duties first
2. Determine: What does this company DO? (Make, install, design, develop software, provide services?)
3. Be SPECIFIC about the industry type
4. Provide 2 plausible alternates if the clues are ambiguous

EXAMPLES:
- "React Developer at fintech startup" → Primary: "fintech SaaS platform", Alternates: ["web development agency", "financial services technology"]
- "CNC Miller" → Primary: "CNC precision machining", Alternates: ["general precision engineering", "automotive component manufacturing"]
- "Data Engineer at healthcare company" → Primary: "healthcare technology / digital health", Alternates: ["data consultancy", "cloud infrastructure services"]
- "Panel Wirer" → Primary: "control panel manufacturing / machine building", Alternates: ["industrial automation", "electrical contractor"]

Rules:
- Return STRICT JSON only
- "primary" = most specific, accurate industry description (2-6 words)
- "alternates" = exactly 2 plausible alternatives
- Use deterministic_hint if provided AND it matches the job function
- DO NOT use generic terms - be specific to what the company does

deterministic_hint: {deterministic_hint}
explicit_sectors: {explicit_sectors}

CLUES JSON:
{json.dumps(clues, indent=2)}

ADVERT (full job description):
{job_description}
"""

    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0
    )
    data = json.loads(r.choices[0].message.content)

    primary = (data.get("primary") or "").strip()
    alternates = data.get("alternates") or []
    if not isinstance(alternates, list):
        alternates = []

    # --- NEW: sanity check using explicit sectors from clues ---
    # If we have explicit sectors and GPT's primary doesn't resemble ANY of them,
    # then don't trust that weird industry – fall back to the first explicit sector.
    if explicit_sectors and primary:
        if not any(es.lower() in primary.lower() or primary.lower() in es.lower()
                   for es in explicit_sectors):
            logger.warning(
                f"⚠️ GPT primary '{primary}' does not match explicit sectors {explicit_sectors}. "
                f"Falling back to first explicit sector."
            )
            primary = explicit_sectors[0]

    # FIX: enforce manufacturing deterministic hint where available
    if deterministic_hint:
        dh = deterministic_hint.strip()
        if dh and any(k in dh.lower() for k in ["manufactur", "fabrication", "production"]):
            logger.info(f"✓ Overriding primary industry with deterministic manufacturing hint: {dh}")
            primary = dh

    # Clean up alternates
    alternates = [a.strip() for a in alternates if isinstance(a, str) and a.strip()]

    # Smart fallback: if we need more alternates, create similar industry names
    fallback_alternates = []
    if len(alternates) < 2 and primary:
        if "cnc" in primary.lower() or "machining" in primary.lower():
            fallback = "precision engineering services"
        elif any(x in primary.lower() for x in ["software", "saas", "tech"]):
            fallback = "technology services"
        elif any(x in primary.lower() for x in ["manufacturing", "fabrication"]):
            fallback = "engineering manufacturing"
        elif any(x in primary.lower() for x in ["financial", "fintech"]):
            fallback = "financial services"
        elif any(x in primary.lower() for x in ["design", "consultancy"]):
            fallback = "professional services"
        else:
            fallback = f"{primary.split()[0]} services" if primary else "related services"

        fallback_alternates.append(fallback)
        logger.warning(f"⚠️ GPT returned <2 alternates, using smart fallback: {fallback}")

    # Pad alternates to exactly 2
    while len(alternates) < 2:
        if fallback_alternates:
            alternates.append(fallback_alternates.pop(0))
        else:
            alternates.append("general services")  # Ultimate fallback

    alternates = alternates[:2]

    if not primary:
        primary = "general services"

    return {
        "primary": primary,
        "alternates": alternates,
        "created_new": False,
        "new_label": None
    }


# ======================================================
# 3) DYNAMIC SEARCH PARAMETER GENERATION
# ======================================================
def generate_search_parameters_for_industry(
    industry_name: str,
    job_description: str,
    machinery_clues: List[str],
    software_clues: List[str]
) -> Dict[str, Any]:
    """
    Uses GPT to dynamically generate search parameters for any industry.
    Returns diagnosing terms, evidence keywords, and blacklist terms specific to this job.
    """

    prompt = f"""
You are generating search parameters to find companies in a specific industry.

For this industry: "{industry_name}"

Based on the job description and clues, generate:

1. **Diagnosing Search Terms** (3-5 terms): The most distinctive keywords that would appear on a company's website in this industry. Be SPECIFIC to this exact job.
   - Use actual brand names, equipment, software, certifications mentioned in the job
   - Examples: "Mazak CNC", "Salesforce CRM", "ISO 9001", "React", "AWS Lambda"
   - Avoid overly generic terms unless nothing specific is available
   - ⚠️ If the industry is MANUFACTURING-related, ensure at least half the terms relate to PHYSICAL production (e.g., "factory", "shop floor", "cnc machining", "sheet metal fabrication") and not just ERP/software.

2. **Evidence Keywords** (5-8 terms): Words/phrases that MUST appear in search results to confirm the company is in this industry
   - Lower case for matching
   - Examples: "cnc", "machining", "press brake", "saas platform", "fintech", "regulated"
   - For manufacturing, include at least some of: "manufacturing", "factory", "production", "fabrication", "assembly".

3. **Blacklist Terms** (3-5 terms): Industries/keywords to EXCLUDE from search results
   - Things that sound similar but are different industries
   - For manufacturing roles, EXCLUDE pure software/IT consulting hits where possible (e.g., "ERP consultancy", "implementation partner", "recruitment agency", "IT services") if that industry is not the target.

INDUSTRY: {industry_name}

MACHINERY/EQUIPMENT CLUES: {', '.join(machinery_clues[:10])}

SOFTWARE/TECH CLUES: {', '.join(software_clues[:10])}

JOB DESCRIPTION (first 1000 chars):
{job_description[:1000]}

Return STRICT JSON:
{{
  "diagnosing_terms": ["term1", "term2", "term3"],
  "evidence_keywords": ["keyword1", "keyword2", ...],
  "blacklist_terms": ["term1", "term2", ...]
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        params = json.loads(response.choices[0].message.content)

        logger.info(f"✓ Generated search params for '{industry_name}': {len(params.get('diagnosing_terms', []))} terms")
        return params

    except Exception as e:
        logger.error(f"Failed to generate search parameters for '{industry_name}': {e}")
        # Fallback to machinery clues if GPT fails
        return {
            "diagnosing_terms": machinery_clues[:3] or [industry_name, "engineering", "company"],
            "evidence_keywords": [industry_name.lower()] + [mc.lower() for mc in machinery_clues[:5]],
            "blacklist_terms": []
        }


# ======================================================
# 4) EVIDENCE FILTER (Dynamic)
# ======================================================
def snippet_has_evidence(
    snippet: str,
    evidence_keywords: List[str],
    unique_clues: List[str],
    require_manufacturing: bool = False
) -> bool:
    """
    Dynamically checks if a search result snippet contains evidence keywords.
    Uses GPT-generated evidence keywords instead of hardcoded dictionary.

    FIX: If require_manufacturing=True, enforce that text clearly refers to
    manufacturing/factory/production, not just ERP/software/consulting.
    """
    if not snippet:
        return False

    txt = snippet.lower()

    # If this role clearly requires a manufacturer, enforce manufacturing words
    if require_manufacturing:
        manuf_words = [
            "manufactur", "factory", "shop floor", "fabrication", "fabricator",
            "cnc", "press brake", "laser cutting", "moulding", "production line",
            "assembly", "sheet metal", "welding", "machinery", "plant"
        ]
        if not any(w in txt for w in manuf_words):
            return False

    # Priority 1: Match against job-specific unique clues (brands, specific equipment)
    if unique_clues and any(uc.lower() in txt for uc in unique_clues):
        return True  # Found the unique differentiator! Keep it.

    # Priority 2: Match against GPT-generated evidence keywords
    if evidence_keywords and any(kw.lower() in txt for kw in evidence_keywords):
        return True

    # No evidence found
    return False


# ======================================================
# 5) NO-PEOPLE-NAMES FILTERS
# ======================================================
LEGAL_SUFFIX_RE = re.compile(
    r"(ltd|limited|plc|llp|inc|group|engineering|manufacturing|systems|fabrications|services|company|co\.?)",
    re.I
)

PERSON_NAME_RE = re.compile(
    r"^(Mr|Ms|Mrs|Dr)?\s*[A-Z][a-z]+(\s[A-Z]\.)?\s*[A-Z][a-z]+$"
)

def is_likely_person(name: str) -> bool:
    if not name:
        return False
    n = name.strip()
    if PERSON_NAME_RE.match(n) and not LEGAL_SUFFIX_RE.search(n):
        return True
    if re.match(r"^[A-Z][a-z]+\s[A-Z][a-z]+$", n) and not LEGAL_SUFFIX_RE.search(n):
        return True
    return False


def redact_people_from_text(text: str) -> str:
    def _repl(match):
        token = match.group(0)
        if LEGAL_SUFFIX_RE.search(token):
            return token
        return "[REDACTED_PERSON]"

    redacted = re.sub(
        r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",
        _repl,
        text
    )
    return redacted


def filter_out_people_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for c in candidates:
        name = (c.get("company_name") or "").strip()
        if is_likely_person(name):
            continue
        cleaned.append(c)
    return cleaned


# ======================================================
# 6) TARGETED SEARCH
# ======================================================
def targeted_search(
    location: str,
    postcode: str,
    industry_name: str,
    search_params: Dict[str, Any],
    unique_clues: List[str],
    multi_site: bool = False
) -> List[Dict[str, Any]]:
    """
    Performs targeted web searches using dynamically generated search parameters.
    """
    if multi_site:
        geo = f"{location} Midlands".strip()
    else:
        geo = f"{location} {postcode}".strip()

    diagnosing_terms = search_params.get("diagnosing_terms", [])
    blacklist_terms = search_params.get("blacklist_terms", [])
    evidence_keywords = search_params.get("evidence_keywords", [])

    # Build exclusion string from dynamic blacklist
    exclude_terms = " ".join(f"-{b}" for b in blacklist_terms) if blacklist_terms else ""

    # Build search queries
    qA = f"{' '.join(diagnosing_terms[:2])} {geo} {exclude_terms}".strip()
    qB = f"\"{industry_name}\" {geo} {exclude_terms}".strip()
    qC = f"{diagnosing_terms[0]} {diagnosing_terms[-1]} {geo} {exclude_terms}".strip() if len(diagnosing_terms) > 1 else qA

    # Unique clue query
    unique_clue_term = " ".join(unique_clues[:2])
    qD = f"\"{unique_clue_term}\" \"{industry_name}\" {geo} {exclude_terms}".strip() if unique_clue_term else ""

    queries = [qA, qB, qC]
    if qD:
        queries.append(qD)

    all_results = []

    for i, q in enumerate(queries, 1):
        logger.info(f"🔍 Targeted Search {i}: {q}")
        try:
            r = tavily_client.search(query=q, max_results=10)
            for res in r.get("results", []):
                res["_query"] = q
                res["_industry"] = industry_name
                res["_evidence_keywords"] = evidence_keywords
                res["_unique_clues"] = unique_clues
                all_results.append(res)
        except Exception as e:
            logger.error(f"Search failed for query '{q}': {e}")

    return all_results


def format_and_filter_results(raw_results: List[Dict[str, Any]]) -> str:
    """
    Evidence filter per-result using that result's industry tag and unique clues.
    Redacts people names.

    FIX: Use require_manufacturing based on industry_name.
    """
    filtered = []
    seen_urls = set()

    for res in raw_results:
        url = res.get("url")
        snippet = (res.get("content") or "")[:800]
        industry_name = res.get("_industry", "Unknown")

        # Dynamically derive if manufacturing evidence is required
        require_manufacturing = any(
            k in industry_name.lower()
            for k in ["manufactur", "fabrication", "production", "cnc", "sheet metal"]
        )

        evidence_keywords = res.get("_evidence_keywords", [])
        unique_clues = res.get("_unique_clues", [])

        if not url or url in seen_urls:
            continue

        if snippet_has_evidence(snippet, evidence_keywords, unique_clues, require_manufacturing=require_manufacturing):
            res["content"] = redact_people_from_text(res.get("content", ""))
            filtered.append(res)
            seen_urls.add(url)

    logger.info(f"✓ Evidence filter kept {len(filtered)}/{len(raw_results)} results across all industry candidates")

    text = f"### FILTERED SEARCH RESULTS (Evidence only)\n\n"
    for idx, res in enumerate(filtered, 1):
        text += f"{idx}. **{res.get('title','N/A')}**\n"
        text += f"   URL: {res.get('url','N/A')}\n"
        text += f"   Industry Candidate: {res.get('_industry','')}\n"
        text += f"   Source Query: {res.get('_query','')}\n"
        text += f"   {res.get('content','N/A')[:600]}...\n\n"

    return text


# ======================================================
# 7) VERIFICATION
# ======================================================
def verify_company(company_name: str, location: str, postcode: str, job_title: str, machinery: str) -> str:
    all_results = f"## Verification for: {company_name}\n\n"

    try:
        q1 = f"{company_name} {location} postcode Companies House"
        r1 = tavily_client.search(query=q1, max_results=3)
        all_results += f"### Location Verification: {q1}\n"
        for res in r1.get("results", []):
            all_results += f"- {res.get('title','N/A')}\n  {res.get('content','N/A')[:200]}...\n"
        all_results += "\n"
    except Exception as e:
        all_results += f"Location search failed: {e}\n\n"

    if machinery:
        try:
            q2 = f"{company_name} {location} {machinery}"
            r2 = tavily_client.search(query=q2, max_results=3)
            all_results += f"### Capability Verification: {q2}\n"
            for res in r2.get("results", []):
                all_results += f"- {res.get('title','N/A')}\n  {res.get('content','N/A')[:200]}...\n"
            all_results += "\n"
        except Exception as e:
            all_results += f"Capability search failed: {e}\n\n"

    try:
        q3 = f"\"{job_title}\" {company_name}"
        r3 = tavily_client.search(query=q3, max_results=3)
        all_results += f"### Job Posting Verification: {q3}\n"
        for res in r3.get("results", []):
            all_results += f"- {res.get('title','N/A')}\n  {res.get('content','N/A')[:200]}...\n"
        all_results += "\n"
    except Exception as e:
        all_results += f"Job posting search failed: {e}\n\n"

    return all_results


# ======================================================
# 8) CLUE EXTRACTION
# ======================================================
def extract_clues_from_job(job_description: str, job_title: str, location: str) -> Dict[str, Any]:
    logger.info(f"Extracting clues from job: {job_title} in {location}")

    system_prompt = """
You are an expert clue extractor for UK recruiter job adverts.

Extract EVERY clue that could help identify the actual hiring company (not the recruiter).
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
"""

    user_content = f"""
JOB TITLE: {job_title}
LOCATION: {location}

FULL JOB DESCRIPTION:
{job_description}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_content}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        clues = json.loads(response.choices[0].message.content)
        clues = extract_dynamic_search_terms(job_description, job_title, clues)
        logger.info("✓ Extracted clues + dynamic search terms")
        return clues

    except Exception as e:
        logger.error(f"Failed to extract clues: {e}")
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


# ======================================================
# Helper: detect physical machinery terms
# ======================================================
def _is_physical_machinery_term(term: str) -> bool:
    if not term:
        return False
    t = term.lower()
    physical_markers = [
        "cnc", "press", "laser", "lathe", "milling", "mill", "turning",
        "weld", "welding", "brake", "shear", "punch", "mould", "molding",
        "robot", "robotic", "production line", "conveyor", "machine",
        "extrusion", "injection", "casting"
    ]
    return any(m in t for m in physical_markers)


# ======================================================
# Helper: outward postcode extraction for geography filter
# ======================================================
def _extract_outward_postcode(pc: str) -> str:
    """
    Extract outward code (e.g. 'LE4' from 'LE4 9EU').
    Returns '' if invalid or not usable.
    """
    if not pc:
        return ""
    pc = pc.strip().upper()
    # Very lightweight: outward code is first token
    return pc.split()[0]


# ======================================================
# 9) COMPANY IDENTIFICATION
# ======================================================
def identify_potential_companies(
    clues: Dict[str, Any],
    job_title: str,
    location: str,
    recruiter_name: str,
    postcode: str = "",
    full_job_description: str = ""
) -> Dict[str, Any]:

    logger.info(f"Identifying potential companies for: {job_title}")

    machinery_clues = clues.get("machinery_clues", []) if clues else []
    software_clues = clues.get("software_clues", []) if clues else []

    unique_clues = list(set(machinery_clues + software_clues))

    location_clues = clues.get("location_clues", {}) if clues else {}
    multi_site = bool(location_clues.get("multi_site", False)) if isinstance(location_clues, dict) else False

    # (1) Infer PRIMARY + 2 alternates, using FULL job description (FIX)
    industry_guess = infer_industry_candidates_with_gpt(clues, full_job_description or clues.get("summary_narrative", ""))
    primary_type = industry_guess["primary"]
    alt_types = industry_guess["alternates"]

    logger.info(f"✓ Industry primary: {primary_type}")
    logger.info(f"✓ Industry alternates: {alt_types}")

    industry_candidates = [primary_type] + alt_types

    # (2) Generate dynamic search parameters for each industry candidate
    job_description_text = full_job_description or clues.get("summary_narrative", "")
    search_params_by_industry = {}

    for industry in industry_candidates:
        params = generate_search_parameters_for_industry(
            industry_name=industry,
            job_description=job_description_text,
            machinery_clues=machinery_clues,
            software_clues=software_clues
        )
        search_params_by_industry[industry] = params
        logger.info(f"✓ Generated params for '{industry}': {params.get('diagnosing_terms', [])}")

    # (3) Targeted search per candidate and merge
    raw_results_all = []
    for industry in industry_candidates:
        raw_results_all.extend(
            targeted_search(
                location=location,
                postcode=postcode,
                industry_name=industry,
                search_params=search_params_by_industry[industry],
                unique_clues=unique_clues,
                multi_site=multi_site
            )
        )

    # (4) Evidence filter BEFORE GPT (merged)
    filtered_search_text = format_and_filter_results(raw_results_all)

    # FIX: choose primary_machinery only from clearly physical terms
    physical_machinery_terms = [t for t in machinery_clues if _is_physical_machinery_term(t)]
    primary_machinery = physical_machinery_terms[0] if physical_machinery_terms else ""

    # (5) Ranking / classification
    system_prompt = f"""
You are an expert in UK industrial geography, manufacturing, and recruitment.

The recruiter is "{recruiter_name}" - NEVER suggest them as the hiring company.

CRITICAL:
- You may ONLY use companies that appear in the FILTERED search results.
- NEVER return individual people names. Only legal entities / companies.

JOB CONTEXT:
- Many of these roles are in PHYSICAL MANUFACTURING environments (factory, shop floor, machines, production lines).
- When the primary industry is manufacturing-like, you MUST distinguish between:
  (a) Companies that actually MAKE physical products (manufacturers)
  (b) Companies that only provide software/services/consulting to manufacturers (ERP providers, IT consultancies, recruitment agencies, etc.)

PRIMARY INDUSTRY: {primary_type}
ALTERNATE INDUSTRIES: {alt_types}

If the job clearly involves factories, production lines, machinery, or shop floors, you MUST:
- Treat non-manufacturers (pure software, ERP consultancy, IT services, recruitment, accountancy) as LOW CONFIDENCE.
- Set is_manufacturer=false and makes_physical_products=false for these.
- They should only appear if there is absolutely no plausible manufacturer at all.

PROCESS:
1) Extract ALL company names from the search results. Ignore people.
2) Pull any address/postcode evidence present.
3) Classify for each company:
   - "is_manufacturer": true/false
   - "makes_physical_products": true/false
4) PRIORITY:
   - STRONGLY prefer companies from PRIMARY industry: {primary_type}
   - Only consider ALTERNATE industries if NO good matches in primary
   - If a company is from an alternate industry, it MUST have exceptional evidence (unique clue match + geography + clear sector fit) to rank highly
   - Add +10 bonus points to total_score for PRIMARY industry matches
5) CRITICALLY: Score match based on unique clues (like {', '.join(unique_clues[:3]) if unique_clues else 'Amada, Hurco, etc.'}) over generic sector/salary matches. A company matching a unique clue MUST score maximum points in the 'unique_clue_match' category.
6) Score geography (radius-based):
   - Exact inward+outward = 10
   - Same outward code = 8
   - Adjacent outward code = 6
   - Same county/cluster = 4
   - Else = 0
7) GEOGRAPHY HARD RULE:
   - The job is located in or around: {location} (postcode: {postcode})
   - If a company is clearly based in a completely different area, its confidence MUST be 0 and it MUST NOT appear in potential_companies at all.
   - If you cannot find any suitable companies in this area, return an empty potential_companies list.

Return STRICT JSON:

{{
  "industrial_cluster": {{
    "location": "Specific town/area from clues",
    "main_sectors": ["{primary_type}"],
    "alt_sectors": {alt_types}
  }},
  "potential_companies": [
    {{
      "company_name": "Company Name Ltd",
      "company_postcode": "LE3 1TU or null",
      "postcode_matches_job": false,
      "location_verified": "Town",
      "is_manufacturer": true,
      "makes_physical_products": true,
      "confidence": 0.85,
      "total_score": 71,
      "score_breakdown": {{
        "geography": 8,
        "sector": 9,
        "multi_site": 6,
        "machinery": 9,
        "narrative": 8,
        "salary": 7,
        "unique_clue_match": 14,
        "primary_industry_bonus": 10
      }},
      "source_search_result": "Result #3",
      "industry_source": "PRIMARY (manufacturing) or ALTERNATE (services/tech)",
      "reasoning": "Evidence + location match. Their website explicitly states they manufacture products in {primary_type}. +10 for primary industry."
    }}
  ],
  "analysis_summary": "Process summary"
}}
"""

    search_params_summary = {}
    for industry, params in search_params_by_industry.items():
        search_params_summary[industry] = params.get("diagnosing_terms", [])

    user_content = f"""
JOB TITLE: {job_title}
LOCATION: {location}
POSTCODE (if provided): {postcode}

PRIMARY INDUSTRY: {primary_type}
ALTERNATE INDUSTRIES: {alt_types}

DIAGNOSING TERMS (by industry):
{json.dumps(search_params_summary, indent=2)}

PRIMARY MACHINERY TERM: {primary_machinery}
ALL UNIQUE CLUES: {', '.join(unique_clues)}

EXTRACTED CLUES:
{json.dumps(clues, indent=2)}

FILTERED SEARCH RESULTS:
{filtered_search_text}

Identify and rank the most likely actual hiring companies.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_content}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        result = json.loads(response.choices[0].message.content)

        # (5b) Optional verify top 3 then re-rank
        top3 = result.get("potential_companies", [])[:3]
        if top3:
            verification_text = ""
            for c in top3:
                verification_text += verify_company(
                    c["company_name"], location, postcode, job_title, primary_machinery
                )

            user_content_2 = user_content + "\n\n### VERIFICATION EVIDENCE:\n" + verification_text
            response2 = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_content_2}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            result = json.loads(response2.choices[0].message.content)

        # (6) HARD post-filter to remove any people names
        pcs = result.get("potential_companies", [])
        pcs = filter_out_people_candidates(pcs)

        # NEW: HARD FILTER non-manufacturers if primary industry is manufacturing-ish
        primary_is_manufacturing = any(
            k in primary_type.lower() for k in ["manufactur", "fabrication", "production", "cnc", "sheet metal"]
        )
        if primary_is_manufacturing:
            before_count = len(pcs)
            pcs = [
                c for c in pcs
                if c.get("is_manufacturer") is True or c.get("makes_physical_products") is True
            ]
            logger.info(
                f"✓ Manufacturing hard-filter removed {before_count - len(pcs)} non-manufacturer candidates "
                f"for manufacturing role."
            )

        # --- NEW: GEOGRAPHY HARD FILTER ---
        job_outward = _extract_outward_postcode(postcode)
        primary_town = ""
        if isinstance(location_clues, dict):
            primary_town = (location_clues.get("primary_town") or "").strip().lower()

        if pcs:
            before_geo = len(pcs)
            geo_filtered: List[Dict[str, Any]] = []
            for c in pcs:
                company_pc = (c.get("company_postcode") or "").strip()
                company_outward = _extract_outward_postcode(company_pc)
                company_loc = (c.get("location_verified") or "").strip().lower()

                # Rule:
                # 1) If we have both job_outward and company_outward → require equality
                # 2) Else if we have primary_town → require town match
                if job_outward and company_outward:
                    if company_outward == job_outward:
                        geo_filtered.append(c)
                elif primary_town:
                    if company_loc and primary_town in company_loc:
                        geo_filtered.append(c)

            pcs = geo_filtered
            logger.info(
                f"✓ Geography hard-filter removed {before_geo - len(pcs)} candidates "
                f"for job postcode='{postcode}' / town='{primary_town}'"
            )

        result["potential_companies"] = pcs

        logger.info(f"✓ Identified {len(pcs)} potential companies after filters")
        for idx, c in enumerate(pcs, 1):
            logger.info(f"  #{idx}: {c.get('company_name')} ({c.get('confidence', 0)*100:.0f}%)")

        return result

    except Exception as e:
        logger.error(f"Failed to identify companies: {e}")
        return {"potential_companies": [], "analysis_summary": f"Error: {str(e)}"}


# ======================================================
# 10) ENRICHMENT
# ======================================================
async def enrich_posting_with_company_id(posting: Dict[str, Any]) -> Dict[str, Any]:
    job_id = posting.get("job_id", "UNKNOWN")
    job_title = posting.get("scraped_job_title", "")
    location = posting.get("job_location_text", "")
    recruiter_name = posting.get("recruiter_name", "")
    full_description = posting.get("full_job_description", "")

    logger.info("=" * 60)
    logger.info(f"Processing job_id={job_id}: {job_title}")

    clues = extract_clues_from_job(full_description, job_title, location)

    postcode = ""
    if clues and "location_clues" in clues:
        postcode = clues["location_clues"].get("postcode", "") or ""

    identification_result = identify_potential_companies(
        clues=clues,
        job_title=job_title,
        location=location,
        recruiter_name=recruiter_name,
        postcode=postcode,
        full_job_description=full_description  # FIX: pass full job description down
    )

    potential_companies = identification_result.get("potential_companies", [])
    industrial_cluster = identification_result.get("industrial_cluster", {})

    all_companies_readable = ""
    if potential_companies:
        company_strings = [
            f"{c.get('company_name','N/A')} ({c.get('confidence',0)*100:.0f}%, "
            f"Score: {c.get('total_score',0)}/60)"
            for c in potential_companies
        ]
        all_companies_readable = " | ".join(company_strings)

    cluster_summary = ""
    if industrial_cluster:
        cl_loc = industrial_cluster.get("location", "N/A")
        sectors = ", ".join(industrial_cluster.get("main_sectors", []))
        cluster_summary = f"{cl_loc}: {sectors}"

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

    logger.info(
        f"✓ Completed: {enriched.get('top_company','No match')} "
        f"({enriched.get('top_confidence',0)*100:.0f}% confidence)"
    )
    return enriched


async def enrich_postings_with_company_identification(postings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched_all: List[Dict[str, Any]] = []
    for posting in postings:
        job_id = posting.get("job_id", "UNKNOWN")
        logger.info(f"🔍 Processing job {job_id}")
        try:
            enriched = await enrich_posting_with_company_id(posting)
            enriched_all.append(enriched)
        except Exception as e:
            logger.error(f"Failed to process job {job_id}: {e}")
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
