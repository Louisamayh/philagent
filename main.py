import os
import csv
import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv
from browser_use import ChatGoogle  # LLM backend for both phases

from scraping_agent import scrape_search_row
from company_matcher import enrich_postings_with_companies

# =========================
# CONFIG
# =========================

# Load env vars (GOOGLE_API_KEY must be in .env)
load_dotenv(override=True)

# Input file: you currently have "input.csv" in the same folder as main.py
INPUT_CSV_PATH = os.getenv("INPUT_CSV", "input.csv")

# Output files: we'll write these (and create the folder if needed)
RAW_OUTPUT_CSV_PATH = os.getenv("RAW_OUTPUT_CSV", "output/jobs_raw.csv")
ENRICHED_OUTPUT_CSV_PATH = os.getenv("ENRICHED_OUTPUT_CSV", "output/jobs_enriched.csv")

# Run bookkeeping dir
RUN_ID = uuid.uuid4().hex[:8]
RUN_DIR = Path(os.getenv("RUN_DIR", f"runs/{RUN_ID}"))
RUN_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_JSONL = RUN_DIR / "checkpoint.jsonl"


# =========================
# INLINE HELPERS
# (these replace io_utils.py)
# =========================

def detect_dialect(path: str) -> csv.Dialect:
    """
    Detect delimiter etc. If sniff fails, fall back to comma.
    """
    with open(path, "rb") as f:
        sample = f.read(4096)

    class _Fallback(csv.Dialect):
        delimiter = ","
        quotechar = '"'
        doublequote = True
        skipinitialspace = True
        lineterminator = "\n"
        quoting = csv.QUOTE_MINIMAL

    try:
        sniffed_text = sample.decode("utf-8", errors="ignore")
        dialect = csv.Sniffer().sniff(sniffed_text)
        return dialect
    except Exception:
        return _Fallback()


def read_input_rows(path: str) -> Tuple[List[List[str]], List[str]]:
    """
    Read the CSV you provide.
    Returns:
      rows  = list of data rows (no header)
      header = the header row (list of column names)
    """
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        all_rows = [r for r in reader if r and any(c.strip() for c in r)]

    if not all_rows:
        raise ValueError("Input CSV appears empty")

    header = all_rows[0]
    rows = all_rows[1:]
    return rows, header


def write_jobs_raw_csv(
    out_path: str,
    dialect: csv.Dialect,
    postings: List[Dict[str, Any]],
):
    """
    First output file:
    One row per scraped job card from CVLibrary.
    Columns:
      job_id
      source_url
      search_job_title
      search_location
      search_radius_miles
      scraped_job_title
      recruiter_name
      job_location_text
      salary_benefits
      description_snippet
      responsibilities_snippet
    """

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "job_id",
        "source_url",
        "search_job_title",
        "search_location",
        "search_radius_miles",
        "scraped_job_title",
        "recruiter_name",
        "job_location_text",
        "salary_benefits",
        "description_snippet",
        "responsibilities_snippet",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(
            f,
            delimiter=getattr(dialect, "delimiter", ","),
            quotechar='"',
            doublequote=True,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerow(header)

        for p in postings:
            writer.writerow([
                p.get("job_id", ""),
                p.get("source_url", ""),
                p.get("search_job_title", ""),
                p.get("search_location", ""),
                p.get("search_radius_miles", ""),
                p.get("scraped_job_title", ""),
                p.get("recruiter_name", ""),
                p.get("job_location_text", ""),
                p.get("salary_benefits", ""),
                p.get("description_snippet", ""),
                p.get("responsibilities_snippet", ""),
            ])


def write_jobs_enriched_csv(
    out_path: str,
    dialect: csv.Dialect,
    enriched_records: List[Dict[str, Any]],
):
    """
    Second output file:
    Same job_id, but now with likely hiring companies.

    Columns:
      job_id
      scraped_job_title
      recruiter_name
      job_location_text
      possible_hiring_company_1
      possible_hiring_company_2
      possible_hiring_company_3
      possible_hiring_company_4
      possible_hiring_company_5
      reasoning
    """

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "job_id",
        "scraped_job_title",
        "recruiter_name",
        "job_location_text",
        "possible_hiring_company_1",
        "possible_hiring_company_2",
        "possible_hiring_company_3",
        "possible_hiring_company_4",
        "possible_hiring_company_5",
        "reasoning",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(
            f,
            delimiter=getattr(dialect, "delimiter", ","),
            quotechar='"',
            doublequote=True,
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerow(header)

        for rec in enriched_records:
            candidates = rec.get("possible_hiring_companies", [])
            # ensure we always have 5 slots
            padded = candidates[:5] + [""] * (5 - len(candidates[:5]))

            writer.writerow([
                rec.get("job_id", ""),
                rec.get("scraped_job_title", ""),
                rec.get("recruiter_name", ""),
                rec.get("job_location_text", ""),
                padded[0],
                padded[1],
                padded[2],
                padded[3],
                padded[4],
                rec.get("reasoning", ""),
            ])


# =========================
# MAIN PIPELINE
# =========================

async def main():
    # sanity check
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY missing. Add it to your .env file.")

    # 1. read input
    rows, header = read_input_rows(INPUT_CSV_PATH)
    dialect = detect_dialect(INPUT_CSV_PATH)

    # map header -> index (relaxed matching)
    norm = [h.strip().lower() for h in header]

    def idx_of(candidates: List[str]) -> int:
        for cand in candidates:
            if cand in norm:
                return norm.index(cand)
        raise ValueError(
            f"Missing required column. Need one of {candidates} in header {header}"
        )

    idx_url = idx_of(["cvlibrary_url", "link", "url"])
    idx_job = idx_of(["job_title", "role", "title"])
    idx_loc = idx_of(["location", "town", "city", "area"])
    idx_miles = idx_of(["miles", "radius_miles", "search_radius", "distance_miles"])

    llm = ChatGoogle(model="gemini-flash-latest")

    all_postings: List[Dict[str, Any]] = []

    # 2. loop searches and scrape CVLibrary
    for row_i, row in enumerate(rows, start=1):
        base_url = (row[idx_url] or "").strip()
        job_title = (row[idx_job] or "").strip()
        location = (row[idx_loc] or "").strip()
        miles = (row[idx_miles] or "").strip()

        if not base_url and not job_title:
            print(f"[{row_i}/{len(rows)}] Skipping blank row")
            continue

        print(f"[{row_i}/{len(rows)}] Searching CVLibrary for '{job_title}' in '{location}' within {miles} miles...")

        postings = await scrape_search_row(
            llm=llm,
            base_url=base_url,
            job_title=job_title,
            location=location,
            miles=miles,
            max_steps=500,
        )

        # stash postings
        all_postings.extend(postings)

        # checkpoint log
        with open(CHECKPOINT_JSONL, "a", encoding="utf-8") as ck:
            ck.write(
                f"{row_i}\t{job_title}\t{len(postings)} jobs scraped\n"
            )

    print(f"📝 Scraped {len(all_postings)} total postings across {len(rows)} searches.")

    # 3. write raw scrape to CSV
    write_jobs_raw_csv(
        RAW_OUTPUT_CSV_PATH,
        dialect,
        all_postings
    )
    print(f"✅ Wrote raw scrape -> {RAW_OUTPUT_CSV_PATH}")

    # 4. infer likely hiring companies for each posting
    enriched_records = await enrich_postings_with_companies(
        llm=llm,
        postings=all_postings,
        max_steps=40,
    )

    # 5. write enriched output
    write_jobs_enriched_csv(
        ENRICHED_OUTPUT_CSV_PATH,
        dialect,
        enriched_records
    )
    print(f"🏁 Wrote enriched employer guesses -> {ENRICHED_OUTPUT_CSV_PATH}")
    print(f"📂 Run ID {RUN_ID}, checkpoints in {CHECKPOINT_JSONL}")


if __name__ == "__main__":
    asyncio.run(main())
