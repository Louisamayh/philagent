"""
Format Phase 3 results into a readable text report
"""
import csv
import json
from pathlib import Path


def format_results(csv_path: str, output_path: str = None):
    """Format Phase 3 CSV results into readable text"""

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        jobs = list(reader)

    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("PHASE 3: COMPANY IDENTIFICATION RESULTS")
    output_lines.append("=" * 80)
    output_lines.append("")

    for idx, job in enumerate(jobs, 1):
        job_title = job.get('scraped_job_title', 'N/A')
        location = job.get('job_location_text', 'N/A')
        recruiter = job.get('recruiter_name', 'N/A')

        # Skip empty jobs
        if not job_title:
            continue

        output_lines.append(f"\n{'=' * 80}")
        output_lines.append(f"JOB #{idx}: {job_title}")
        output_lines.append(f"{'=' * 80}")
        output_lines.append(f"Location: {location}")
        output_lines.append(f"Recruiter: {recruiter}")
        output_lines.append("")

        # Parse potential companies JSON
        try:
            companies = json.loads(job.get('potential_companies', '[]'))

            if companies:
                output_lines.append(f"POTENTIAL HIRING COMPANIES ({len(companies)} identified):")
                output_lines.append("")

                for comp_idx, company in enumerate(companies, 1):
                    name = company.get('company_name', 'N/A')
                    confidence = company.get('confidence', 0.0) * 100
                    reasoning = company.get('reasoning', 'N/A')

                    output_lines.append(f"  {comp_idx}. {name}")
                    output_lines.append(f"     Confidence: {confidence:.0f}%")
                    output_lines.append(f"     Reasoning: {reasoning}")
                    output_lines.append("")
            else:
                output_lines.append("  No potential companies identified")
                output_lines.append("")

            # Overall analysis
            analysis = job.get('analysis_summary', '')
            if analysis:
                output_lines.append(f"OVERALL ANALYSIS:")
                output_lines.append(f"{analysis}")
                output_lines.append("")

        except json.JSONDecodeError as e:
            output_lines.append(f"  Error parsing companies: {e}")
            output_lines.append("")

    # Print to console
    result_text = "\n".join(output_lines)
    print(result_text)

    # Save to file if requested
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result_text)
        print(f"\n\n✓ Saved formatted results to: {output_path}")

    return result_text


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = "output/phase3_test_results.csv"

    if not Path(csv_path).exists():
        print(f"Error: File not found: {csv_path}")
        sys.exit(1)

    # Generate output filename
    output_path = csv_path.replace('.csv', '_formatted.txt')

    format_results(csv_path, output_path)
