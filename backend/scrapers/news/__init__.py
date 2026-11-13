from backend.scrapers.news.common import ExistingUrlsResolver, PageItemsCallback
from backend.scrapers.news.indiatv import scrape_indiatv_latest
from backend.scrapers.news.indianexpress import scrape_indianexpress_latest
from backend.scrapers.news.livemint import scrape_livemint_latest
from backend.scrapers.news.news18 import scrape_news18_latest
from backend.scrapers.news.common import ScrapedNewsItem

__all__ = [
    "ScrapedNewsItem",
    "ExistingUrlsResolver",
    "PageItemsCallback",
    "scrape_indianexpress_latest",
    "scrape_livemint_latest",
    "scrape_news18_latest",
    "scrape_indiatv_latest",
]
