from backend.infra.postgres.tables.application import Application
from backend.infra.postgres.tables.base import Base
from backend.infra.postgres.tables.bookmark import Bookmark
from backend.infra.postgres.tables.cold_email_draft import ColdEmailDraft
from backend.infra.postgres.tables.professor_research_cache import ProfessorResearchCache
from backend.infra.postgres.tables.chat_message import ChatMessage
from backend.infra.postgres.tables.chat_thread import ChatThread
from backend.infra.postgres.tables.news_article import NewsArticle
from backend.infra.postgres.tables.opportunity import Opportunity
from backend.infra.postgres.tables.user import User
from backend.infra.postgres.tables.user_coldemail_profile import UserColdEmailProfile
from backend.infra.postgres.tables.user_professor_history import UserProfessorHistory
from backend.infra.postgres.tables.user_settings import UserSettings

__all__ = [
	"Base",
	"Opportunity",
	"Bookmark",
	"Application",
	"UserSettings",
	"User",
	"ChatThread",
	"ChatMessage",
	"NewsArticle",
	"ColdEmailDraft",
	"ProfessorResearchCache",
	"UserColdEmailProfile",
	"UserProfessorHistory",
]
