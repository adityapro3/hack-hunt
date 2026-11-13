from backend.scrapers.hackathons.devfolio import DevfolioScraper
from backend.scrapers.hackathons.hack2skill import Hack2skillScraper
from backend.scrapers.hackathons.hackearth import HackerearthScraper
from backend.scrapers.hackathons.kaggle import KaggleScraper
from backend.scrapers.hackathons.neurips import NeurIPSScraper
from backend.scrapers.hackathons.unstop import UnstopScraper

__all__ = [
	"DevfolioScraper",
	"UnstopScraper",
	"HackerearthScraper",
	"Hack2skillScraper",
	"KaggleScraper",
	"NeurIPSScraper",
]
