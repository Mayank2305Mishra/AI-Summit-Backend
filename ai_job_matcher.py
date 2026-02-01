from typing import List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI

def calculate_skill_overlap(
    job_requirements: List[str], student_skills: List[str]
) -> Dict:
    """
    Calculate skill overlap percentage.
    Returns: { "overlap": [], "missing": [], "percentage": float }
    """
    # Normalize skills to lowercase for better matching
    job_skills_set = set([skill.lower().strip() for skill in job_requirements])
    student_skills_set = set([skill.lower().strip() for skill in student_skills])

    overlap = job_skills_set.intersection(student_skills_set)
    missing = job_skills_set - student_skills_set

    if len(job_skills_set) > 0:
        match_percentage = (len(overlap) / len(job_skills_set)) * 100
    else:
        match_percentage = 100

    return {
        "overlap": list(overlap),
        "missing": list(missing),
        "percentage": match_percentage,
    }

def generate_ai_match_reasoning(
    job: Dict, artifact_pack, skill_match: Dict, api_key: str
) -> str:
    """
    Use LLM to generate detailed match reasoning.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0,
        google_api_key=api_key,
    )

    prompt = f"""Analyze this job match and provide a brief 2-3 sentence reasoning for why this is a good or poor match.

JOB:
Title: {job['title']}
Company: {job['company']}
Requirements: {', '.join(job.get('requirements', []))}
Description: {job.get('description', '')}

STUDENT PROFILE:
Skills: {', '.join(artifact_pack.profile.skills)}
Projects: {len(artifact_pack.profile.projects)} projects
Internships: {len(artifact_pack.profile.internships)} internships

MATCH DATA:
Skill Overlap: {len(skill_match['overlap'])}/{len(job.get('requirements', []))} required skills
Matching Skills: {', '.join(skill_match['overlap'])}
Missing Skills: {', '.join(skill_match['missing'])}

Provide concise reasoning (2-3 sentences max) explaining the match quality."""

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception:
        return "AI reasoning unavailable."