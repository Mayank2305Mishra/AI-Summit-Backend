from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class Project(BaseModel):
    """Model for project information"""

    name: str = Field(
        description="Exact project name as it appears in source - VERBATIM ONLY, no modifications"
    )
    description: str = Field(
        description="Factual description using ONLY words from source - NO adjectives like 'innovative', 'scalable', 'robust', 'production-ready'"
    )
    tech: List[str] = Field(
        default_factory=list,
        description="Technologies EXPLICITLY named in source - NOT inferred from context or project type",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="URLs found in source that prove this project - must be actual links from resume/GitHub/portfolio",
    )


class Internship(BaseModel):
    """Model for internships and work experience"""

    role: str = Field(
        description="Job title EXACTLY as written - no inflation, no modification (e.g., 'Intern' stays 'Intern', not 'Software Engineer')"
    )
    company: str = Field(
        description="Company name EXACTLY as written - no additions or modifications"
    )
    duration: Optional[str] = Field(
        default=None,
        description="Time period ONLY if explicitly stated - DO NOT estimate or calculate",
    )
    description: str = Field(
        description="Responsibilities using ONLY words from source - no embellishment, no inferred achievements or impact"
    )
    location: Optional[str] = Field(
        default=None,
        description="Work location ONLY if explicitly mentioned - leave null if not stated",
    )


class Constraints(BaseModel):
    """Student constraints and preferences"""

    location: Optional[str] = Field(
        default=None,
        description="Preferred location ONLY if explicitly stated - DO NOT assume from current location",
    )
    remote: Optional[bool] = Field(
        default=None,
        description="Remote preference ONLY if explicitly stated - leave null if ambiguous or not mentioned",
    )
    visa: Optional[str] = Field(
        default=None,
        description="Visa/work authorization using EXACT wording - DO NOT infer from nationality or location",
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Available start date ONLY if explicitly provided - DO NOT estimate from graduation date",
    )
    relocation: Optional[str] = Field(
        default=None,
        description="Relocation willingness using EXACT wording - DO NOT assume openness",
    )


class StudentProfile(BaseModel):
    """Structured student facts - ABSOLUTE ZERO INFERENCE"""

    education: List[str] = Field(
        default_factory=list,
        description="Degrees/institutions/years EXACTLY as written - include GPA ONLY if mentioned, NEVER assume honors/rankings/dean's list",
    )
    projects: List[Project] = Field(
        default_factory=list,
        description="Projects from source - use EXACT names and descriptions, NO quality inferences, NO assumed scale",
    )
    internships: List[Internship] = Field(
        default_factory=list,
        description="Work experiences with EXACT titles - NEVER inflate 'Intern' to 'Engineer', NEVER add seniority not stated",
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Skills EXPLICITLY listed as skills - NEVER extract from project descriptions, NEVER infer from tech stack",
    )
    links: List[str] = Field(
        default_factory=list,
        description="All URLs found in source - no invented or assumed links, only actual URLs present",
    )
    constraints: Constraints = Field(
        default_factory=Constraints,
        description="ALL fields null unless explicitly stated - do not infer from context",
    )


class BulletBankItem(BaseModel):
    """Normalized achievement bullet - traceable to source"""

    bullet: str = Field(
        description="Achievement using ONLY verifiable facts - NO metrics unless explicitly stated, NO quality words ('innovative', 'scalable', 'efficient', 'improved', 'optimized')"
    )
    source_type: Literal["project", "internship", "education"] = Field(
        description="Must match an actual item type in profile"
    )
    source_name: str = Field(
        description="EXACT name from profile - must be traceable back to specific project/internship/education item"
    )
    is_quantified: bool = Field(
        default=False,
        description="True ONLY if bullet contains a number that appeared in source - NEVER estimate percentages, user counts, or performance gains",
    )


class AnswerLibrary(BaseModel):
    """Reusable answers - EXACT wording only"""

    work_authorization: Optional[str] = Field(
        default=None,
        description="Use EXACT wording from source (e.g., 'US Citizen', 'Requires sponsorship') - NEVER assume from nationality",
    )
    availability: Optional[str] = Field(
        default=None,
        description="Start date using EXACT wording - leave null if not explicitly mentioned, NEVER estimate",
    )
    relocation: Optional[str] = Field(
        default=None,
        description="Relocation using EXACT wording - leave null if not stated, NEVER assume willingness",
    )
    salary_expectations: Optional[str] = Field(
        default=None,
        description="ONLY if explicitly provided - NEVER estimate or suggest based on role/location",
    )
    remote_preference: Optional[str] = Field(
        default=None,
        description="Remote preference using EXACT wording - leave null if not explicitly stated",
    )


class ProofPack(BaseModel):
    """Evidence links from source material"""

    link: str = Field(
        description="URL that was actually found in source - must be real link from resume/GitHub/portfolio"
    )
    type: Literal[
        "portfolio", "demo", "github", "case_study", "publication", "other"
    ] = Field(description="Type based on URL domain/content")
    title: str = Field(
        description="Title using EXACT naming from source - no creative renaming"
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief description using ONLY information from source - no assumptions about functionality or quality",
    )


class ArtifactPack(BaseModel):
    """Student Artifact Pack - ZERO HALLUCINATION"""

    profile: StudentProfile = Field(
        description="VERBATIM extraction only - every field must be traceable to source"
    )
    bullet_bank: List[BulletBankItem] = Field(
        default_factory=list,
        description="5-15 bullets - each must be traceable to specific profile item, NO invented achievements",
    )
    answer_library: AnswerLibrary = Field(
        default_factory=AnswerLibrary,
        description="EXACT wording from source - all fields null unless explicitly found",
    )
    proof_pack: List[ProofPack] = Field(
        default_factory=list,
        description="3-8 strongest links - must be actual URLs found in source material",
    )
