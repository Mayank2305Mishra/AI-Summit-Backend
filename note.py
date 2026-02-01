from typing import List, Dict


def _score_bullet_against_job(bullet_text: str, job_requirements: List[str]) -> int:
    """
    Simple keyword overlap score between bullet and job requirements.
    Deterministic and explainable.
    """
    bullet_text = bullet_text.lower()
    score = 0

    for req in job_requirements:
        if req.lower() in bullet_text:
            score += 1

    return score


def _clean_text(text: str) -> str:
    """
    Normalize whitespace and line breaks.
    """
    return " ".join(text.replace("\n", " ").split())


def generate_recruiter_notes(
    artifact: Dict, jobs: List[Dict], max_bullets: int = 3
) -> List[Dict]:
    """
    Generates short recruiter notes (facts-only) for each job.
    """

    bullet_bank = artifact["bullet_bank"]
    results = []

    for job in jobs:
        # HARD SAFETY GATE
        if not job.get("automation_allowed", False):
            continue

        job_requirements = job.get("requirements", [])

        scored_bullets = []

        for bullet in bullet_bank:
            score = _score_bullet_against_job(bullet["bullet"], job_requirements)
            if score > 0:
                scored_bullets.append((score, bullet["bullet"]))

        # Sort bullets by relevance
        scored_bullets.sort(reverse=True, key=lambda x: x[0])

        # Fallback if nothing matched
        if not scored_bullets:
            scored_bullets = [(0, b["bullet"]) for b in bullet_bank[:2]]

        selected_bullets = [
            _clean_text(bullet) for _, bullet in scored_bullets[:max_bullets]
        ]

        short_note = ". ".join(selected_bullets)

        # Hard cap for recruiter skim
        short_note = short_note[:600]

        results.append({"job_id": job["job_id"], "short_note": short_note})

    return results
