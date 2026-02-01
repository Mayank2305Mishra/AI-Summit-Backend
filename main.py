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

        result = analyze_resume_data(data_pool)

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
    gemini_api_key: str = Form(..., description="Google Gemini API Key"),
    top_k: Optional[int] = Form(30, description="Number of top matches to return"),
    min_similarity: Optional[float] = Form(
        0.3, description="Minimum similarity threshold (0-1)"
    ),
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
            api_key=gemini_api_key,
            jobs_file_path=jobs_file,
            top_k=top_k,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
