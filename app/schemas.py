from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Claim(Strict):
    text: str = Field(min_length=1, max_length=1500)
    source_turn_ids: list[str] = Field(min_length=1, max_length=20)


class Note(Strict):
    subjective: list[Claim] = Field(max_length=100)
    objective: list[Claim] = Field(max_length=100)
    assessment: list[Claim] = Field(max_length=100)
    plan: list[Claim] = Field(max_length=100)


class Generate(Strict):
    title: str = Field(
        default="Untitled synthetic encounter", min_length=1, max_length=100
    )
    transcript: str = Field(min_length=10, max_length=18000)
    provider: Literal["demo", "openai", "ollama"] = "demo"
    prompt_version: Literal["grounded-v2", "baseline-v1", "corrections-v3"] = (
        "grounded-v2"
    )
    synthetic_confirmed: Literal[True]


class Review(Strict):
    note: Note
    revision: int = Field(ge=1)
    reviewer: str = Field(min_length=1, max_length=80)
    comment: str = Field(default="", max_length=1000)
    approve: bool = False
    review_confirmed: bool = False


class EvalRequest(Strict):
    provider: Literal["demo", "openai", "ollama"] = "demo"
    prompt_version: Literal["grounded-v2", "baseline-v1", "corrections-v3"] = (
        "grounded-v2"
    )
    limit: int = Field(default=30, ge=1, le=30)
