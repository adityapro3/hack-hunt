from dataclasses import dataclass


@dataclass
class MatchedPublication:
    title: str
    score: float
    year: int | None
    detail_url: str | None
    abstract: str | None
