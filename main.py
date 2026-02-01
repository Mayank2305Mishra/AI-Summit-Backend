from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import tempfile
import os
from models import ArtifactPack
from data_extraction import (
    extract_resume_text,
    fetch_github,
    scrape_page,
    ingest_linkedin,
    build_data_pool,
    analyze_resume_data,
)
from note import generate_recruiter_notes
from models import ArtifactPack
from matching import (
    match_jobs_with_ai,
    create_ai_apply_queue,
    load_jobs_from_file,
    filter_automatable_jobs,
)
import json
from typing import Optional

app = FastAPI(
    title="AI Summit 2026",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "status": "OK",
    }


@app.post("/analyze", response_model=ArtifactPack)
async def analyze_resume(
    resume: UploadFile = File(..., description="Resume PDF file"),
    github_username: Optional[str] = Form(None, description="GitHub username"),
    portfolio_url: Optional[str] = Form(None, description="Portfolio website URL"),
    linkedin_text: Optional[str] = Form(None, description="LinkedIn profile text"),
    gemini_api_key: str = Form(..., description="Google Gemini API Key")
):
    if not resume.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await resume.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        resume_text = extract_resume_text(tmp_file_path)
        os.unlink(tmp_file_path)
        github_data = None
        if github_username:
            try:
                github_data = fetch_github(github_username)
            except Exception as e:
                print(f"Error fetching GitHub data: {e}")
                github_data = None
        portfolio_pages = None
        if portfolio_url:
            try:
                portfolio_pages = scrape_page(portfolio_url)
            except Exception as e:
                print(f"Error scraping portfolio: {e}")
                portfolio_pages = None
        linkedin_processed = ingest_linkedin(linkedin_text) if linkedin_text else None
        data_pool = build_data_pool(
            resume_text=resume_text,
            linkedin_text=linkedin_processed,
            github_data=github_data,
            portfolio_pages=portfolio_pages,
            project_links=[],
        )

        result = analyze_resume_data(data_pool, gemini_api_key)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing resume: {str(e)}")


@app.post("/extract-text")
async def extract_text_from_resume(
    resume: UploadFile = File(..., description="Resume PDF file")
):
    if not resume.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await resume.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        text = extract_resume_text(tmp_file_path)

        os.unlink(tmp_file_path)

        return {"text": text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting text: {str(e)}")

@app.get("/github/{username}")
async def get_github_data(username: str):
    try:
        data = fetch_github(username)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching GitHub data: {str(e)}"
        )


@app.post("/scrape")
async def scrape_portfolio(url: str = Form(..., description="Portfolio URL to scrape")):
    try:
        data = scrape_page(url)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping page: {str(e)}")


@app.post("/match-jobs-ai")
async def match_jobs_with_ai_endpoint(
    artifact_pack: str = Form(..., description="JSON string of Student artifact pack"),
    top_k: Optional[int] = Form(30, description="Number of top matches to return"),
    min_similarity: Optional[float] = Form(
        0.3, description="Minimum similarity threshold (0-1)"
    ),
    api_key: str = Form(..., description="Google Gemini API Key"),
    jobs_file: Optional[str] = Form("jobs.json", description="Path to jobs.json file"),
):
    try:
        # 1. Manually parse the JSON string into the Pydantic model
        try:
            artifact_data = json.loads(artifact_pack)
            artifact_obj = ArtifactPack(**artifact_data)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid ArtifactPack JSON: {str(e)}"
            )

        # 2. Use the parsed object in your matching function
        matches = await match_jobs_with_ai(
            artifact_pack=artifact_obj,
            jobs_file_path=jobs_file,
            top_k=top_k,
            api_key=api_key,
            min_similarity=min_similarity,
        )

        apply_queue = create_ai_apply_queue(matches)

        return {
            "status": "success",
            "method": "ai_vector_embeddings",
            "apply_queue": apply_queue,
            "metadata": {
                "total_analyzed": len(matches),
                "top_k": top_k,
                "min_similarity": min_similarity,
                "average_match": apply_queue["average_match_score"],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI matching failed: {str(e)}")


@app.post("/explain-match")
async def explain_job_match(
    job_id: str = Form(..., description="Job ID to explain"),
    artifact_pack: ArtifactPack = None,
    gemini_api_key: str = Form(..., description="Google Gemini API Key"),
    jobs_file: Optional[str] = Form("jobs.json", description="Path to jobs.json"),
):
    """
    Get detailed AI explanation for why a specific job matches the student

    Args:
        job_id: Job ID to explain (e.g., "job_001")
        artifact_pack: Student artifact pack
        gemini_api_key: Google Gemini API key
        jobs_file: Path to jobs.json

    Returns:
        Detailed match explanation with AI reasoning
    """
    try:
        from ai_job_matcher import calculate_skill_overlap, generate_ai_match_reasoning

        # Load jobs
        all_jobs = load_jobs_from_file(jobs_file)
        job = next((j for j in all_jobs if j["job_id"] == job_id), None)

        if not job:
            raise HTTPException(
                status_code=404, detail=f"Job {job_id} not found in {jobs_file}"
            )

        # Calculate skill match
        skill_match = calculate_skill_overlap(
            job.get("requirements", []), artifact_pack.profile.skills
        )

        # Generate AI reasoning
        reasoning = generate_ai_match_reasoning(
            job, artifact_pack, skill_match, gemini_api_key
        )

        return {
            "job_id": job_id,
            "job_title": job["title"],
            "company": job["company"],
            "skill_overlap": skill_match["overlap"],
            "missing_skills": skill_match["missing"],
            "skill_match_percentage": skill_match["percentage"],
            "ai_explanation": reasoning,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to explain match: {str(e)}"
        )


@app.get("/jobs/stats")
async def get_jobs_stats(jobs_file: Optional[str] = "jobs.json"):
    """
    Get statistics about jobs.json

    Args:
        jobs_file: Path to jobs.json (default: "jobs.json")

    Returns:
        Total jobs, automatable jobs, categories, experience levels, etc.
    """
    try:
        all_jobs = load_jobs_from_file(jobs_file)
        automatable = filter_automatable_jobs(all_jobs)

        # Count by category
        tech_jobs = len([j for j in automatable if j.get("category") == "tech"])
        non_tech_jobs = len([j for j in automatable if j.get("category") == "non-tech"])

        # Count by experience level
        intern_jobs = len(
            [j for j in automatable if j.get("experience_level") == "Intern"]
        )
        entry_jobs = len(
            [j for j in automatable if j.get("experience_level") == "Entry"]
        )

        # Count by location
        remote_jobs = len(
            [j for j in automatable if j.get("location", "").lower() == "remote"]
        )

        return {
            "total_jobs": len(all_jobs),
            "automatable_jobs": len(automatable),
            "non_automatable_jobs": len(all_jobs) - len(automatable),
            "tech_jobs": tech_jobs,
            "non_tech_jobs": non_tech_jobs,
            "intern_positions": intern_jobs,
            "entry_positions": entry_jobs,
            "remote_jobs": remote_jobs,
            "file_path": jobs_file,
        }

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Jobs file not found: {jobs_file}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading jobs: {str(e)}")


@app.post("/generate-short-notes-from-queue")
async def generate_short_notes_from_apply_queue(
    artifact_pack: str = Form(..., description="JSON string of Student artifact pack"),
    apply_queue: str = Form(..., description="Full JSON output of /match-jobs-ai"),
    jobs_file: Optional[str] = Form("jobs.json", description="Path to jobs.json file"),
):
    """
    Generate short recruiter notes from apply_queue output
    (output of /match-jobs-ai).
    """

    try:
        # -----------------------------------
        # Parse ArtifactPack
        # -----------------------------------
        try:
            artifact_data = json.loads(artifact_pack)
            artifact_obj = ArtifactPack(**artifact_data)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid ArtifactPack JSON: {str(e)}"
            )

        # -----------------------------------
        # Parse apply_queue (FIXED STRUCTURE)
        # -----------------------------------
        try:
            apply_queue_data = json.loads(apply_queue)

            queue = apply_queue_data.get("apply_queue")
            if not queue:
                raise ValueError("Missing 'apply_queue' key")

            job_entries = queue.get("jobs", [])
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid apply_queue JSON structure: {str(e)}"
            )

        if not job_entries:
            raise HTTPException(
                status_code=400, detail="apply_queue.apply_queue.jobs is empty"
            )

        # -----------------------------------
        # Extract job_ids
        # -----------------------------------
        job_ids = []
        for entry in job_entries:
            if "job_id" in entry:
                job_ids.append(entry["job_id"])

        if not job_ids:
            raise HTTPException(
                status_code=400, detail="No job_ids found in apply_queue.jobs"
            )

        # -----------------------------------
        # Load jobs.json
        # -----------------------------------
        all_jobs = load_jobs_from_file(jobs_file)

        selected_jobs = [
            job
            for job in all_jobs
            if job["job_id"] in job_ids and job.get("automation_allowed", False)
        ]

        if not selected_jobs:
            raise HTTPException(
                status_code=404, detail="No automatable jobs found in apply_queue"
            )

        # -----------------------------------
        # Generate recruiter notes
        # -----------------------------------
        from note import generate_recruiter_notes

        notes = generate_recruiter_notes(
            artifact=artifact_obj.model_dump(), jobs=selected_jobs
        )

        # -----------------------------------
        # Final Response
        # -----------------------------------
        return {
            "status": "success",
            "input_jobs": len(job_ids),
            "automatable_jobs": len(selected_jobs),
            "generated_notes": len(notes),
            "notes": notes,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recruiter notes from apply_queue: {str(e)}",
        )


@app.post("/sandbox-apply-batch")
async def sandbox_apply_batch(
    artifact_pack: str = Form(..., description="Student ArtifactPack JSON"),
    recruiter_notes: str = Form(
        ..., description="Output JSON from /generate-short-notes-from-queue"
    ),
    apply_queue: str = Form(..., description="Output JSON from /match-jobs-ai"),
):
    """
    Final sandbox recruiter simulator.
    Uses:
    - student artifacts
    - recruiter notes (generated earlier)
    - apply_queue (job matches + scores)

    Returns:
    list of job_id + signal (success | processing | failure)
    """

    try:
        # -----------------------------
        # Parse inputs
        # -----------------------------
        artifact = ArtifactPack(**json.loads(artifact_pack))
        notes_payload = json.loads(recruiter_notes)
        queue_payload = json.loads(apply_queue)

        job_entries = queue_payload["apply_queue"]["jobs"]
        notes_list = notes_payload.get("notes", [])

        # Build job_id -> short_note map
        notes_map = {n["job_id"]: n["short_note"] for n in notes_list}

        results = []

        # -----------------------------
        # Process each job entry
        # -----------------------------
        for entry in job_entries:
            job = entry["job"]
            job_id = job["job_id"]

            # HARD SAFETY GATE
            if not job.get("automation_allowed", False):
                results.append({"job_id": job_id, "signal": "failure"})
                continue

            # -----------------------------
            # Extract & normalize scores
            # -----------------------------
            semantic = entry.get("semantic_similarity", 0) / 100
            skill = entry.get("skill_match_score", 0) / 100
            match = entry.get("match_score", 0) / 100

            # Base confidence (reuse Part-2 signals)
            confidence = 0.40 * semantic + 0.35 * skill + 0.25 * match

            # -----------------------------
            # Recruiter-note sanity check
            # -----------------------------
            note = notes_map.get(job_id, "").lower()
            matched_terms = sum(
                1 for req in job.get("requirements", []) if req.lower() in note
            )

            # Penalize slightly if note is weak
            if matched_terms == 0:
                confidence *= 0.85

            confidence = round(confidence, 3)

            # -----------------------------
            # Decision thresholds
            # -----------------------------
            if confidence >= 0.25:
                signal = "success"
            elif confidence >= 0.23:
                signal = "processing"
            else:
                signal = "failure"

            results.append(
                {"job_id": job_id, "signal": signal, "confidence": confidence}
            )

        return {"status": "success", "total_jobs": len(results), "results": results}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Sandbox batch apply failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
