import json
import faiss
from typing import List, Dict, Optional
from pydantic import BaseModel
import uuid
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import os
from dotenv import load_dotenv
from langchain_community.docstore.in_memory import InMemoryDocstore
load_dotenv()

class JobMatch(BaseModel):
    """Job match result with AI-powered scoring"""

    job_id: str
    job: Dict
    match_score: float
    semantic_similarity: float
    skill_match_score: float
    ai_reasoning: str
    relevant_bullets: List[str]
    priority: str


def load_jobs_from_file(jobs_file_path: str = "jobs.json") -> List[Dict]:
    """Load jobs from JSON file"""
    with open(jobs_file_path, "r") as f:
        jobs_data = json.load(f)

    if isinstance(jobs_data, dict) and "jobs" in jobs_data:
        return jobs_data["jobs"]
    elif isinstance(jobs_data, list):
        return jobs_data
    else:
        raise ValueError("Invalid jobs.json format")


def filter_automatable_jobs(jobs: List[Dict]) -> List[Dict]:
    """Filter jobs where automation_allowed = true"""
    return [job for job in jobs if job.get("automation_allowed", True)]


def create_student_profile_text(artifact_pack) -> str:
    """
    Create a comprehensive text representation of student profile for embedding
    """
    profile = artifact_pack.profile

    # Build profile text
    sections = []

    # Education
    if profile.education:
        sections.append("EDUCATION:\n" + "\n".join(profile.education))

    # Skills
    if profile.skills:
        sections.append("SKILLS:\n" + ", ".join(profile.skills))

    # Projects
    if profile.projects:
        projects_text = []
        for project in profile.projects:
            tech = ", ".join(project.tech) if project.tech else ""
            projects_text.append(f"{project.name}: {project.description} ({tech})")
        sections.append("PROJECTS:\n" + "\n".join(projects_text))

    # Internships
    if profile.internships:
        internships_text = []
        for internship in profile.internships:
            internships_text.append(
                f"{internship.role} at {internship.company}: {internship.description}"
            )
        sections.append("EXPERIENCE:\n" + "\n".join(internships_text))

    # Bullet Bank
    if artifact_pack.bullet_bank:
        bullets_text = [item.bullet for item in artifact_pack.bullet_bank]
        sections.append("ACHIEVEMENTS:\n" + "\n".join(bullets_text))

    return "\n\n".join(sections)


def create_job_documents(jobs: List[Dict]) -> List[Document]:
    """
    Convert jobs to LangChain Documents for vector storage
    """
    documents = []

    for job in jobs:
        # Create comprehensive job text
        job_text_parts = [
            f"Title: {job['title']}",
            f"Company: {job['company']}",
            f"Category: {job.get('category', 'tech')}",
            f"Experience Level: {job.get('experience_level', 'Entry')}",
            f"Location: {job.get('location', 'Remote')}",
            f"Description: {job.get('description', '')}",
            f"Requirements: {', '.join(job.get('requirements', []))}",
        ]

        job_text = "\n".join(job_text_parts)

        # Create document with metadata
        doc = Document(
            page_content=job_text,
            metadata={
                "job_id": job["job_id"],
                "title": job["title"],
                "company": job["company"],
                "category": job.get("category", "tech"),
                "experience_level": job.get("experience_level", "Entry"),
                "location": job.get("location", "Remote"),
                "requirements": job.get("requirements", []),
                "automation_allowed": job.get("automation_allowed", True),
                "full_job": job,
            },
        )
        documents.append(doc)

    return documents


def create_vector_store(jobs: List[Dict], embeddings):
    """
    Create FAISS vector store from jobs using newer initialization syntax
    """
    # Create documents
    documents = create_job_documents(jobs)

    # Initialize FAISS index
    embedding_dimension = len(embeddings.embed_query("hello world"))
    index = faiss.IndexFlatL2(embedding_dimension)

    # Create vector store with newer syntax
    vectorstore = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

    # Add documents to vector store
    vectorstore.add_documents(documents)

    return vectorstore


def calculate_skill_overlap(
    job_requirements: List[str], student_skills: List[str]
) -> Dict:
    """Calculate skill overlap percentage"""
    job_skills_set = set([skill.lower() for skill in job_requirements])
    student_skills_set = set([skill.lower() for skill in student_skills])

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


def get_relevant_bullets_semantic(
    job_text: str, bullet_bank: List, embeddings, top_k: int = 5
) -> List[str]:
    """
    Find most relevant bullets using semantic similarity with newer FAISS syntax
    """
    if not bullet_bank:
        return []

    # Extract bullet texts
    bullet_texts = [item.bullet for item in bullet_bank]

    # Create documents for bullets
    bullet_docs = [Document(page_content=text) for text in bullet_texts]

    # Initialize FAISS index for bullets
    embedding_dimension = len(embeddings.embed_query("hello world"))
    index = faiss.IndexFlatL2(embedding_dimension)

    # Create bullet vector store with newer syntax
    bullet_store = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )

    # Add bullet documents
    bullet_store.add_documents(bullet_docs)

    # Find most similar bullets to job description
    results = bullet_store.similarity_search(job_text, k=min(top_k, len(bullet_texts)))

    return [doc.page_content for doc in results]


def generate_ai_match_reasoning(
    job: Dict, artifact_pack, skill_match: Dict, api_key: str
) -> str:
    """
    Use LLM to generate detailed match reasoning
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

    response = llm.invoke(prompt)
    return response.content



async def match_jobs_with_ai(
    artifact_pack,
    jobs_file_path: str = "jobs.json",
    top_k: int = 30,
    api_key: str = "",
    min_similarity: float = 0.3,
) -> List[JobMatch]:
    """
    Main AI-powered job matching function using vector embeddings

    Args:
        artifact_pack: Student artifact pack
        api_key: Google Gemini API key
        jobs_file_path: Path to jobs.json
        top_k: Number of top matches to return
        min_similarity: Minimum similarity score threshold (0-1)

    Returns:
        List of JobMatch objects sorted by relevance
    """
    # 1. Load and filter jobs
    all_jobs = load_jobs_from_file(jobs_file_path)
    automatable_jobs = filter_automatable_jobs(all_jobs)

    print(f"Loaded {len(automatable_jobs)} automatable jobs")

    # 2. Create student profile text for embedding
    student_text = create_student_profile_text(artifact_pack)

    # 3. Initialize embeddings
    print("Initializing embeddings...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key,
    )

    # 4. Create vector store from jobs
    print("Creating vector embeddings for jobs...")
    vectorstore = create_vector_store(automatable_jobs, embeddings)

    # 5. Perform semantic similarity search
    print("Finding semantically similar jobs...")
    results = vectorstore.similarity_search_with_score(
        student_text,
        k=min(top_k * 2, len(automatable_jobs)),  # Get more initially, filter later
    )

    # 6. Process each match
    matches = []
    for doc, similarity_score in results:
        # Similarity score from FAISS is distance (lower = better)
        # Convert to similarity (0-1, higher = better)
        semantic_similarity = 1 - similarity_score

        # Skip if below threshold
        if semantic_similarity < min_similarity:
            continue

        job = doc.metadata["full_job"]

        # Calculate skill match
        skill_match = calculate_skill_overlap(
            job.get("requirements", []), artifact_pack.profile.skills
        )

        # Get relevant bullets using semantic search
        relevant_bullets = get_relevant_bullets_semantic(
            doc.page_content, artifact_pack.bullet_bank, embeddings, top_k=5
        )

        # Calculate combined score
        # 60% semantic similarity + 40% skill match
        skill_match_score = skill_match["percentage"] / 100
        combined_score = (semantic_similarity * 0.6) + (skill_match_score * 0.4)
        match_score = combined_score * 100

        # Generate AI reasoning
        try:
            ai_reasoning = generate_ai_match_reasoning(
                job, artifact_pack, skill_match, api_key
            )
        except Exception as e:
            ai_reasoning = f"Semantic similarity: {semantic_similarity:.2%}, Skill match: {skill_match_score:.2%}"

        # Determine priority
        if match_score >= 70:
            priority = "high"
        elif match_score >= 50:
            priority = "medium"
        else:
            priority = "low"

        # Create match object
        job_match = JobMatch(
            job_id=job["job_id"],
            job=job,
            match_score=round(match_score, 2),
            semantic_similarity=round(semantic_similarity * 100, 2),
            skill_match_score=round(skill_match_score * 100, 2),
            ai_reasoning=ai_reasoning,
            relevant_bullets=relevant_bullets,
            priority=priority,
        )

        matches.append(job_match)

    # 7. Sort by match score
    matches.sort(key=lambda x: x.match_score, reverse=True)

    # 8. Return top k
    return matches[:top_k]


def create_ai_apply_queue(matches: List[JobMatch]) -> Dict:
    """
    Create structured apply queue from AI matches
    """
    return {
        "total_jobs": len(matches),
        "high_priority": len([m for m in matches if m.priority == "high"]),
        "medium_priority": len([m for m in matches if m.priority == "medium"]),
        "low_priority": len([m for m in matches if m.priority == "low"]),
        "average_match_score": (
            round(sum(m.match_score for m in matches) / len(matches), 2)
            if matches
            else 0
        ),
        "jobs": [
            {
                "job_id": m.job_id,
                "job": m.job,
                "match_score": m.match_score,
                "semantic_similarity": m.semantic_similarity,
                "skill_match_score": m.skill_match_score,
                "ai_reasoning": m.ai_reasoning,
                "relevant_bullets": m.relevant_bullets,
                "priority": m.priority,
            }
            for m in matches
        ],
    }
