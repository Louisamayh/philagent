"""
FastAPI server for PhilAgent web interface.
Provides REST API for job scraping with configurable instructions.
"""

import os
import json
import asyncio
import uuid
import signal
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import existing functionality
from browser_use import ChatGoogle
from main import detect_dialect
from link_collector import collect_links_from_single_page, save_links_to_csv
from job_scraper import scrape_jobs_from_links
from company_matcher import enrich_postings_with_companies, EnrichedPosting

# Initialize FastAPI app
app = FastAPI(title="PhilAgent API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage paths
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
FINAL_OUTPUT_DIR = Path("final_output")
RUNS_DIR = Path("runs")
CONFIG_FILE = Path("config.json")

# Ensure directories exist
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
FINAL_OUTPUT_DIR.mkdir(exist_ok=True)
RUNS_DIR.mkdir(exist_ok=True)

# Global job tracking
active_jobs: Dict[str, Dict[str, Any]] = {}
active_tasks: Dict[str, asyncio.Task] = {}


# ==================== Data Models ====================

class Instruction(BaseModel):
    """Single instruction for the scraping agent"""
    text: str = Field(..., description="Instruction text")
    order: int = Field(..., description="Execution order")


class JobConfig(BaseModel):
    """Configuration for a job run"""
    instructions: List[Instruction] = Field(
        default_factory=list,
        description="List of instructions for the agent"
    )
    scraping_enabled: bool = Field(True, description="Enable scraping phase")
    enrichment_enabled: bool = Field(True, description="Enable company enrichment")


class JobStatus(BaseModel):
    """Status of a running or completed job"""
    job_id: str
    status: str  # 'queued', 'running', 'completed', 'failed'
    progress: int = 0  # 0-100
    message: str = ""
    created_at: str
    completed_at: Optional[str] = None
    input_file: Optional[str] = None
    output_files: Dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class JobStartRequest(BaseModel):
    """Request to start a new job"""
    input_filename: str
    config: JobConfig


# ==================== Configuration Management ====================

def load_default_config() -> JobConfig:
    """Load default configuration from file or create new"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return JobConfig(**data)

    # Default configuration
    return JobConfig(
        instructions=[
            Instruction(text="Navigate to CV-Library", order=1),
            Instruction(text="Enter job title and location from input", order=2),
            Instruction(text="Extract job postings from search results", order=3),
        ],
        scraping_enabled=True,
        enrichment_enabled=True
    )


def save_config(config: JobConfig):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)


# ==================== CSV Helper Functions ====================

def read_input_rows(path: str) -> List[Dict[str, str]]:
    """Read and parse input CSV file"""
    import csv

    dialect = detect_dialect(path)

    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, dialect=dialect)
        rows = []
        for row in reader:
            # Normalize keys to lowercase
            normalized_row = {k.lower().strip(): v for k, v in row.items() if k}
            rows.append(normalized_row)

    return rows


def write_jobs_raw_csv(out_path: str, postings: List[Dict[str, Any]]):
    """Write raw scraped jobs to CSV"""
    import csv

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"DEBUG: write_jobs_raw_csv called with {len(postings)} postings")
    print(f"DEBUG: Output path: {out_path}")

    # Always create the file, even if empty, so user knows it ran
    # if not postings:
    #     print("WARNING: No postings to write, but creating empty CSV file anyway")
    #     # return

    fieldnames = [
        "job_id", "source_url", "search_job_title", "search_location",
        "search_radius_miles", "scraped_job_title", "recruiter_name",
        "job_location_text", "salary_benefits", "description_snippet",
        "responsibilities_snippet"
    ]

    try:
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(postings)
        print(f"✓ Successfully wrote {len(postings)} rows to {out_path}")
    except Exception as e:
        print(f"ERROR: Failed to write CSV to {out_path}: {e}")
        import traceback
        traceback.print_exc()
        raise


def write_jobs_enriched_csv(out_path: str, enriched: List[Dict[str, Any]]):
    """Write enriched jobs with company inferences to CSV"""
    import csv

    if not enriched:
        return

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Flatten the possible_hiring_companies list into separate columns
    rows_to_write = []
    for rec in enriched:
        companies = rec.get("possible_hiring_companies", [])
        row = {
            "job_id": rec.get("job_id", ""),
            "scraped_job_title": rec.get("scraped_job_title", ""),
            "recruiter_name": rec.get("recruiter_name", ""),
            "job_location_text": rec.get("job_location_text", ""),
            "possible_hiring_company_1": companies[0] if len(companies) > 0 else "",
            "possible_hiring_company_2": companies[1] if len(companies) > 1 else "",
            "possible_hiring_company_3": companies[2] if len(companies) > 2 else "",
            "possible_hiring_company_4": companies[3] if len(companies) > 3 else "",
            "possible_hiring_company_5": companies[4] if len(companies) > 4 else "",
            "reasoning": rec.get("reasoning", ""),
        }
        rows_to_write.append(row)

    fieldnames = [
        "job_id", "scraped_job_title", "recruiter_name", "job_location_text",
        "possible_hiring_company_1", "possible_hiring_company_2",
        "possible_hiring_company_3", "possible_hiring_company_4",
        "possible_hiring_company_5", "reasoning"
    ]

    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)


# ==================== Job Execution ====================

async def run_job(job_id: str, input_file: Path, config: JobConfig):
    """
    Execute a complete job run with TWO-PHASE scraping and enrichment.
    Phase 1: Collect all job links (max 5 pages per search)
    Phase 2: Scrape each link for full details (autosave every 25 jobs)
    Updates job status in active_jobs dictionary.
    """
    all_postings: List[Dict[str, Any]] = []
    raw_output_path = FINAL_OUTPUT_DIR / f"{job_id}_jobs_raw.csv"

    try:
        # Initialize LLM
        llm = ChatGoogle(model="gemini-flash-latest")

        # Update status
        active_jobs[job_id]["status"] = "running"
        active_jobs[job_id]["message"] = "Reading input file..."
        active_jobs[job_id]["progress"] = 10

        # Read input CSV
        input_rows = read_input_rows(str(input_file))

        if not input_rows:
            raise ValueError("No valid rows found in input file")

        # Set up output file paths
        active_jobs[job_id]["output_files"]["raw"] = str(raw_output_path)
        links_output_path = OUTPUT_DIR / f"{job_id}_links.csv"
        active_jobs[job_id]["output_files"]["links"] = str(links_output_path)

        if config.scraping_enabled:
            active_jobs[job_id]["message"] = f"Processing {len(input_rows)} searches..."

            for idx, row in enumerate(input_rows):
                # Check if job was cancelled
                if job_id not in active_jobs:
                    print(f"Job {job_id} was cancelled")
                    return

                # Extract fields from row (with flexible column names)
                base_url = (
                    row.get("cvlibrary_url") or
                    row.get("link") or
                    row.get("url") or
                    "www.cv-library.co.uk"
                ).strip()

                job_title = (
                    row.get("job_title") or
                    row.get("role") or
                    row.get("title") or
                    ""
                ).strip()

                location = (
                    row.get("location") or
                    row.get("town") or
                    row.get("city") or
                    row.get("area") or
                    ""
                ).strip()

                miles = (
                    row.get("miles") or
                    row.get("radius_miles") or
                    row.get("search_radius") or
                    row.get("distance_miles") or
                    "30"
                ).strip()

                if not job_title:
                    continue

                search_info = {
                    "job_title": job_title,
                    "location": location,
                    "miles": miles
                }

                # ===== PHASE 1: COLLECT LINKS PAGE-BY-PAGE (max 5 pages) =====
                active_jobs[job_id]["message"] = f"PHASE 1: Collecting links for search {idx + 1}/{len(input_rows)}"
                active_jobs[job_id]["progress"] = 10 + int(20 * (idx / len(input_rows)))

                all_links_for_search = []
                current_page_url = None

                # Loop through pages 1-5
                for page_num in range(1, 6):  # Pages 1, 2, 3, 4, 5
                    # Check if job was cancelled
                    if job_id not in active_jobs:
                        print(f"Job {job_id} was cancelled")
                        return

                    active_jobs[job_id]["message"] = f"PHASE 1: Page {page_num}/5 for search {idx + 1}/{len(input_rows)}"

                    try:
                        # Increase max_steps for later pages (they take longer to navigate to)
                        page_max_steps = 150 if page_num == 1 else 200

                        # Collect links from this page
                        result = await collect_links_from_single_page(
                            llm=llm,
                            base_url=base_url,
                            job_title=job_title,
                            location=location,
                            miles=miles,
                            page_number=page_num,
                            search_url=current_page_url,
                            max_steps=page_max_steps
                        )

                        page_links = result.get("links", [])
                        current_page_url = result.get("current_page_url", "")

                        if page_links:
                            all_links_for_search.extend(page_links)

                            # AUTOSAVE after each page
                            append_mode = (page_num > 1)  # Append for pages 2-5, overwrite for page 1
                            save_links_to_csv(page_links, str(links_output_path), search_info, append=append_mode)
                            print(f"✓ Page {page_num}: Saved {len(page_links)} links (Total: {len(all_links_for_search)})")

                            # Warn if page has suspiciously few links (might have stopped mid-task)
                            if len(page_links) < 10 and page_num <= 3:
                                print(f"⚠ WARNING: Page {page_num} only returned {len(page_links)} links (expected ~25)")
                                print(f"⚠ Agent may have stopped mid-task. Check logs/link_collection_*.log")
                        else:
                            # No links found on this page, might be the last page
                            print(f"⚠ Page {page_num}: No links found, stopping pagination")
                            if page_num <= 2:
                                print(f"⚠ WARNING: Stopped early on page {page_num}. This might be an error!")
                                print(f"⚠ Check logs/link_collection_*.log for details")
                            break

                    except Exception as page_err:
                        print(f"Error collecting page {page_num} for search {idx + 1}: {page_err}")
                        # Continue to next page or stop if this was a critical error
                        break

                if not all_links_for_search:
                    print(f"⚠ No links collected from search {idx + 1}")
                    continue

                print(f"✓ PHASE 1 Complete: Collected {len(all_links_for_search)} total links from search {idx + 1}")

                # ===== PHASE 2: SCRAPE EACH LINK =====
                # Read links from the CSV that Phase 1 just saved
                from job_scraper import read_links_from_csv, scrape_single_job

                try:
                    links, csv_search_info = read_links_from_csv(str(links_output_path))
                    print(f"✓ PHASE 2: Read {len(links)} links from CSV for search {idx + 1}")
                except Exception as read_err:
                    print(f"Error reading links CSV: {read_err}")
                    continue

                if not links:
                    print(f"⚠ No links found in CSV for search {idx + 1}")
                    continue

                active_jobs[job_id]["message"] = f"PHASE 2: Scraping {len(links)} jobs for search {idx + 1}/{len(input_rows)}"
                active_jobs[job_id]["progress"] = 30 + int(20 * (idx / len(input_rows)))

                try:
                    # Scrape jobs one by one with autosave every 25 jobs
                    search_postings = []
                    for link_idx, link in enumerate(links):
                        # Check if job was cancelled
                        if job_id not in active_jobs:
                            print(f"Job {job_id} was cancelled")
                            return

                        job_url = link.get("link_url", "")
                        if not job_url:
                            continue

                        active_jobs[job_id]["message"] = f"Scraping job {link_idx + 1}/{len(links)} from search {idx + 1}/{len(input_rows)}"

                        try:
                            job_data = await scrape_single_job(
                                llm=llm,
                                job_url=job_url,
                                search_info=csv_search_info,
                                max_steps=50
                            )
                            search_postings.append(job_data)
                            all_postings.append(job_data)

                            # Auto-save every 25 jobs
                            if len(all_postings) % 25 == 0:
                                write_jobs_raw_csv(str(raw_output_path), all_postings)
                                print(f"📝 Auto-saved after {len(all_postings)} jobs")

                        except Exception as job_err:
                            print(f"Error scraping job {link_idx + 1}: {job_err}")
                            continue

                    print(f"✓ Scraped {len(search_postings)} jobs from search {idx + 1}")

                except Exception as scrape_err:
                    print(f"Error in Phase 2 for search {idx + 1}: {scrape_err}")
                    continue

            active_jobs[job_id]["progress"] = 50
            active_jobs[job_id]["message"] = f"Scraped {len(all_postings)} jobs total"

            # Final write to catch any remaining postings
            write_jobs_raw_csv(str(raw_output_path), all_postings)
            print(f"✓ Final save: {len(all_postings)} total jobs")

        # Phase 3: Enrichment
        enriched_postings: List[Dict[str, Any]] = []
        enriched_output_path = FINAL_OUTPUT_DIR / f"{job_id}_jobs_enriched.csv"
        enriched_partial_path = FINAL_OUTPUT_DIR / f"{job_id}_jobs_enriched_partial.csv"

        if config.enrichment_enabled:
            # Read Phase 2 output from CSV
            phase2_postings = []
            if raw_output_path.exists():
                try:
                    phase2_postings = read_input_rows(str(raw_output_path))
                    print(f"✓ PHASE 3: Read {len(phase2_postings)} jobs from Phase 2 output")
                except Exception as read_err:
                    print(f"Error reading Phase 2 output: {read_err}")
                    phase2_postings = []

            if not phase2_postings:
                print("⚠ No jobs found in Phase 2 output, skipping enrichment")
            else:
                active_jobs[job_id]["message"] = f"Enriching {len(phase2_postings)} jobs..."
                active_jobs[job_id]["output_files"]["enriched"] = str(enriched_output_path)
                active_jobs[job_id]["output_files"]["enriched_partial"] = str(enriched_partial_path)

                # Process enrichment in batches with auto-save
                batch_size = 10
                for i in range(0, len(phase2_postings), batch_size):
                    # Check if job was cancelled
                    if job_id not in active_jobs:
                        print(f"Job {job_id} was cancelled during enrichment")
                        return

                    batch = phase2_postings[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(phase2_postings) + batch_size - 1) // batch_size

                    active_jobs[job_id]["message"] = f"Enriching batch {batch_num}/{total_batches} ({len(enriched_postings) + len(batch)}/{len(phase2_postings)} jobs)..."
                    active_jobs[job_id]["progress"] = 50 + int(40 * (i / len(phase2_postings)))

                    try:
                        # Enrich this batch
                        batch_enriched = await enrich_postings_with_companies(
                            llm=llm,
                            postings=batch,
                            max_steps=50  # Allow enough steps for web search
                        )
                        enriched_postings.extend(batch_enriched)

                        # Auto-save to PARTIAL file after each batch
                        write_jobs_enriched_csv(str(enriched_partial_path), enriched_postings)
                        print(f"📝 Auto-saved {len(enriched_postings)} enriched postings to partial file")

                    except Exception as enrich_err:
                        print(f"Error enriching batch {batch_num}: {enrich_err}")
                        import traceback
                        traceback.print_exc()
                        # Continue with next batch even if this one fails

                # Final save to main enriched file
                write_jobs_enriched_csv(str(enriched_output_path), enriched_postings)
                print(f"✓ Final save: {len(enriched_postings)} enriched jobs")

                active_jobs[job_id]["progress"] = 90
                active_jobs[job_id]["message"] = f"Enriched {len(enriched_postings)} jobs"

        # Complete
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["progress"] = 100
        active_jobs[job_id]["message"] = f"Job completed: {len(all_postings)} jobs scraped"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except asyncio.CancelledError:
        # Job was cancelled by user
        print(f"Job {job_id} was cancelled")
        if job_id in active_jobs:
            # Save partial results before stopping
            if all_postings:
                try:
                    write_jobs_raw_csv(str(raw_output_path), all_postings)
                    print(f"Saved {len(all_postings)} partial results before stopping")
                    active_jobs[job_id]["message"] = f"Job stopped by user - saved {len(all_postings)} results"
                except Exception as save_err:
                    print(f"Failed to save partial results: {save_err}")
                    active_jobs[job_id]["message"] = "Job stopped by user"
            else:
                active_jobs[job_id]["message"] = "Job stopped by user"

            active_jobs[job_id]["status"] = "stopped"
            active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        raise  # Re-raise to properly cancel the task
    except Exception as e:
        # Check if job still exists (user may have stopped/deleted it)
        if job_id in active_jobs:
            # Try to save partial results before marking as failed
            if all_postings:
                try:
                    write_jobs_raw_csv(str(raw_output_path), all_postings)
                    print(f"Saved {len(all_postings)} partial results before failure")
                    active_jobs[job_id]["message"] = f"Job failed but saved {len(all_postings)} results: {str(e)}"
                except Exception as save_err:
                    print(f"Failed to save partial results: {save_err}")
                    active_jobs[job_id]["message"] = f"Job failed: {str(e)}"
            else:
                active_jobs[job_id]["message"] = f"Job failed: {str(e)}"

            active_jobs[job_id]["status"] = "failed"
            active_jobs[job_id]["error"] = str(e)
            active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        print(f"Job {job_id} failed: {str(e)}")
    finally:
        # Clean up task reference
        if job_id in active_tasks:
            del active_tasks[job_id]


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Serve the main HTML page"""
    return FileResponse("static/index.html")


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    config = load_default_config()
    return config


@app.post("/api/config")
async def update_config(config: JobConfig):
    """Update configuration"""
    save_config(config)
    return {"message": "Configuration saved successfully"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload input CSV file"""
    try:
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        filename = f"{file_id}_{file.filename}"
        file_path = UPLOAD_DIR / filename

        # Save file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)

        return {
            "filename": filename,
            "size": len(content),
            "message": "File uploaded successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/jobs/start")
async def start_job(request: JobStartRequest):
    """Start a new job with given configuration"""
    try:
        # Validate input file exists
        input_path = UPLOAD_DIR / request.input_filename
        if not input_path.exists():
            raise HTTPException(status_code=404, detail="Input file not found")

        # Create job
        job_id = str(uuid.uuid4())

        # Initialize job status
        active_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Job queued",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "input_file": request.input_filename,
            "output_files": {},
            "error": None,
        }

        # Save config
        save_config(request.config)

        # Start job in background and store task
        task = asyncio.create_task(run_job(job_id, input_path, request.config))
        active_tasks[job_id] = task

        return {"job_id": job_id, "message": "Job started successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return active_jobs[job_id]


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return list(active_jobs.values())


@app.get("/api/download/{job_id}/{file_type}")
async def download_output(job_id: str, file_type: str):
    """Download output file (raw or enriched)"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    if file_type not in job["output_files"]:
        raise HTTPException(status_code=404, detail=f"Output file '{file_type}' not found")

    file_path = job["output_files"][file_type]

    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        file_path,
        filename=f"{job_id}_{file_type}.csv",
        media_type="text/csv"
    )


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Stop and delete a job and its outputs"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = active_jobs[job_id]

    # Cancel the running task if it exists
    if job_id in active_tasks:
        task = active_tasks[job_id]
        task.cancel()
        try:
            await task  # Wait for task to finish cancellation
        except asyncio.CancelledError:
            pass  # Expected

    # Delete output files
    for file_path in job["output_files"].values():
        try:
            Path(file_path).unlink(missing_ok=True)
        except:
            pass

    # Remove from active jobs
    del active_jobs[job_id]

    return {"message": "Job stopped and deleted successfully"}


@app.post("/api/shutdown")
async def shutdown():
    """Shutdown the PhilAgent server"""
    # Cancel all active tasks
    for job_id, task in list(active_tasks.items()):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Clear all jobs
    active_jobs.clear()
    active_tasks.clear()

    # Schedule shutdown after response is sent
    async def delayed_shutdown():
        await asyncio.sleep(0.5)  # Give time for response to be sent
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(delayed_shutdown())

    return {"message": "PhilAgent shutting down..."}


# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🚀 PhilAgent Web Interface Starting...")
    print("=" * 60)
    print(f"📂 Upload directory: {UPLOAD_DIR.absolute()}")
    print(f"📂 Output directory: {OUTPUT_DIR.absolute()}")
    print(f"🌐 Open your browser to: http://localhost:8000")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
