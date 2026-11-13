from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScrapedOpportunity:
    opportunity_type: str = "Hackathon"
    title: str = ""
    url: str = ""
    source: str = ""
    description: str | None = None
    domains: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    mode: str | None = None
    location: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    deadline: datetime | None = None
    prize_money: str | None = None
    registration_fee: str | None = None
    team_size: str | None = None
    eligibility: list[str] = field(default_factory=list)
    status: str = "Active"

@dataclass
class ScrapedNewsItem:
    source: str
    topic: str
    title: str
    url: str
    content: str
    published_at: datetime | None


class BaseScraper(ABC):
    source: str

    @abstractmethod
    async def scrape(self) -> list[ScrapedOpportunity]:
        raise NotImplementedError
