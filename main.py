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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
