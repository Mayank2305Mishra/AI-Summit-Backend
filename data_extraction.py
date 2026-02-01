import pdfplumber
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import system_prompt_data_extraction
from models import ArtifactPack
from dotenv import load_dotenv
import os
load_dotenv()   

def extract_resume_text(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def fetch_github(username: str) -> Dict:
    profile = requests.get(f"https://api.github.com/users/{username}").json()
    repos = requests.get(f"https://api.github.com/users/{username}/repos").json()

    clean_repos = []
    for r in repos:
        clean_repos.append(
            {
                "name": r.get("name", ""),
                "description": r.get("description", ""),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language", ""),
                "url": r.get("html_url", ""),
            }
        )

    return {
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "followers": profile.get("followers"),
            "url": profile.get("html_url"),
        },
        "repos": clean_repos,
    }


def classify_links(links: List[Dict]) -> Dict[str, List]:
    buckets = {
        "linkedin": [],
        "github_profile": [],
        "projects": [],
        "notebooks": [],
        "research_papers": [],
        "others": [],
    }

    for l in links:
        url = l["url"].lower()
        text = (l.get("text") or "").lower()

        # LinkedIn
        if "linkedin.com/in" in url:
            buckets["linkedin"].append(l)

        # GitHub Profile
        elif "github.com" in url and len(urlparse(url).path.strip("/").split("/")) == 1:
            buckets["github_profile"].append(l)

        # GitHub Repos / Projects
        elif "github.com" in url:
            buckets["projects"].append(l)

        # Notebooks
        elif any(
            x in url
            for x in [
                "colab.research.google.com",
                "kaggle.com",
                "nbviewer.org",
                ".ipynb",
            ]
        ):
            buckets["notebooks"].append(l)

        # Research Papers
        elif any(
            x in url
            for x in [
                "arxiv.org",
                "ieee.org",
                "springer.com",
                "acm.org",
                "researchgate.net/publication",
                "semanticscholar.org",
                ".pdf",
            ]
        ) and any(k in text for k in ["paper", "publication", "research", "journal"]):
            buckets["research_papers"].append(l)

        else:
            buckets["others"].append(l)

    return buckets


def scrape_page(url: str) -> Dict:
    r = requests.get(
        url,
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ResumeAnalyzerBot/1.0)"},
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove junk
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    # Visible text
    text = " ".join(soup.stripped_strings)

    # Extract and normalize links
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(url, href)  # handles relative links

        links.append({"text": a.get_text(strip=True), "url": full_url})

    # Remove duplicates
    unique_links = []
    seen = set()
    for l in links:
        if l["url"] not in seen:
            seen.add(l["url"])
            unique_links.append(l)

    unique_links = classify_links(unique_links)

    return {"url": url, "text": text[:8000], "links": unique_links}  # Limit text length


def ingest_linkedin(text: str) -> str:
    return text.strip()


def build_data_pool(
    resume_text: Optional[str],
    linkedin_text: Optional[str],
    github_data: Optional[Dict],
    portfolio_pages: Optional[Dict],
    project_links: List[str],
) -> Dict:
    return {
        "resume_text": resume_text,
        "linkedin_text": linkedin_text,
        "github": github_data,
        "portfolio_pages": portfolio_pages,
        "project_links": project_links,
    }


def analyze_resume_data(data_pool: Dict) -> ArtifactPack:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-lite",
        temperature=0,
        api_key="AIzaSyDZqc2Dgqi2dFbLuA1eJSzvfvS7SXij-fQ",
    )
    llm_structured = llm.with_structured_output(ArtifactPack)
    message = [
        ("system", system_prompt_data_extraction),
        ("user", f"Student Data to Process:\n\n{data_pool}"),
    ]

    response = llm_structured.invoke(message)

    return response
