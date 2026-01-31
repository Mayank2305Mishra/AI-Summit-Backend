from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class Project(BaseModel):
    name: str = Field(
        description="Exact project name as mentioned in resume, GitHub, or portfolio"
    )
    description: str = Field(
        description="Fact-only description of what was built - NO inferred qualities"
    )
    tech: List[str] = Field(
        default_factory=list,
        description="Technologies explicitly mentioned for this project",
    )
    evidence: List[str] = Field(
        default_factory=list, description="URLs that prove this project exists"
    )


class Internship(BaseModel):
    role: str = Field(description="Exact job title as stated")
    company: str = Field(description="Company or organization name")
    duration: Optional[str] = Field(
        default=None,
        description="Time period if mentioned (e.g., 'Summer 2024', 'Jan 2024 - Present')",
    )
    description: str = Field(
        description="Fact-only responsibilities - NO embellishment"
    )
    location: Optional[str] = Field(
        default=None, description="Work location if mentioned"
    )


class Constraints(BaseModel):
    location: Optional[str] = Field(
        default=None, description="Preferred work location if stated"
    )
    remote: Optional[bool] = Field(
        default=None, description="Remote work preference if stated"
    )
    visa: Optional[str] = Field(
        default=None, description="Visa status or work authorization if mentioned"
    )
    start_date: Optional[str] = Field(
        default=None, description="Available start date if provided"
    )
    relocation: Optional[str] = Field(
        default=None, description="Willingness to relocate if stated"
    )


class StudentProfile(BaseModel):
    education: List[str] = Field(
        default_factory=list,
        description="Degrees, institutions, and years EXACTLY as stated - include GPA only if mentioned",
    )
    projects: List[Project] = Field(
        default_factory=list,
        description="All projects from resume, GitHub, or portfolio - facts only",
    )
    internships: List[Internship] = Field(
        default_factory=list,
        description="Internships and work experiences - exact titles and companies only",
    )
    skills: List[str] = Field(
        default_factory=list,
        description="Technical skills EXPLICITLY mentioned - NO inferred skills from project descriptions",
    )
    links: List[str] = Field(
        default_factory=list,
        description="All URLs from resume, GitHub, LinkedIn, or portfolio",
    )
    constraints: Constraints = Field(
        default_factory=Constraints,
        description="Location, visa, remote preferences, start date - only if explicitly stated",
    )


class BulletBankItem(BaseModel):
    bullet: str = Field(
        description="Achievement bullet grounded in verifiable facts - NO invented metrics or qualities"
    )
    source_type: Literal["project", "internship", "education"] = Field(
        description="Type of source this bullet comes from"
    )
    source_name: str = Field(
        description="Exact name of project, company, or institution"
    )
    is_quantified: bool = Field(
        default=False,
        description="True only if bullet contains a number explicitly stated in source material",
    )


class AnswerLibrary(BaseModel):
    work_authorization: Optional[str] = Field(
        default=None,
        description="Work authorization status - use EXACT wording if provided (e.g., 'US Citizen', 'Requires H1B sponsorship')",
    )
    availability: Optional[str] = Field(
        default=None,
        description="When student can start - use exact date or timeframe if mentioned",
    )
    relocation: Optional[str] = Field(
        default=None,
        description="Willingness to relocate - use exact statement if provided",
    )
    salary_expectations: Optional[str] = Field(
        default=None,
        description="Salary expectations - ONLY if explicitly provided by student",
    )
    remote_preference: Optional[str] = Field(
        default=None, description="Remote work preference - ONLY if explicitly stated"
    )


class ProofPack(BaseModel):
    link: str = Field(
        description="URL to portfolio item, demo, GitHub repo, or case study"
    )
    type: Literal[
        "portfolio", "demo", "github", "case_study", "publication", "other"
    ] = Field(description="Type of proof")
    title: str = Field(description="Title or name of the artifact")
    description: Optional[str] = Field(
        default=None, description="Brief factual description of what this proves"
    )


class ArtifactPack(BaseModel):
    profile: StudentProfile = Field(
        description="Structured student facts - FACTS ONLY, NO INFERENCE"
    )
    bullet_bank: List[BulletBankItem] = Field(
        default_factory=list,
        description="Normalized achievement bullets tied to specific projects/experiences - 5 to 15 bullets",
    )
    answer_library: AnswerLibrary = Field(
        default_factory=AnswerLibrary,
        description="Reusable answers for common application questions",
    )
    proof_pack: List[ProofPack] = Field(
        default_factory=list,
        description="3 to 8 links that back up claims - portfolio, demos, GitHub repos, case studies",
    )
