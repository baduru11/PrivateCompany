# backend/nodes/synthesis.py
from __future__ import annotations
from backend.config import get_llm
from backend.models import CompanyProfile, ExploreReport, DeepDiveReport

EXPLORE_SYSTEM = """You are a competitive intelligence analyst. Given company profiles,
create a structured competitive landscape report.
CRITICAL: Only include information from the provided data. Write 'Data not available' for missing fields. Never guess."""

DEEP_DIVE_SYSTEM = """You are a competitive intelligence analyst. Given company data,
create a detailed intelligence report with these sections: Overview, Funding History,
Key People, Product/Technology, Recent News, Competitors, Red Flags.
CRITICAL: Only include information from the provided data. If data is missing, explicitly
state 'Data not available' in that section. Never infer, guess, or use your own knowledge.
For each section, set confidence based on how much source data supports it."""


def synthesize(state: dict) -> dict:
    llm = get_llm()
    mode = state["mode"]
    profiles = state["company_profiles"]

    profiles_text = "\n\n".join(
        p.model_dump_json(indent=2) if hasattr(p, "model_dump_json")
        else str(p)
        for p in profiles
    )

    if mode == "explore":
        structured_llm = llm.with_structured_output(ExploreReport)
        report = structured_llm.invoke([
            {"role": "system", "content": EXPLORE_SYSTEM},
            {"role": "user", "content": f"Query: {state['query']}\n\nCompany profiles:\n{profiles_text}"}
        ])
    else:
        structured_llm = llm.with_structured_output(DeepDiveReport)
        report = structured_llm.invoke([
            {"role": "system", "content": DEEP_DIVE_SYSTEM},
            {"role": "user", "content": f"Company: {state['query']}\n\nCollected data:\n{profiles_text}"}
        ])

    return {"report": report}
