from backend.services.opportunities.chat import (
    generate_opportunity_chat_response,
    generate_opportunity_chat_response_stream,
)
from backend.services.opportunities.models import ChatContextItem, ChatServiceResult
from backend.services.opportunities.query import (
    get_opportunity_filters,
    get_opportunity_or_raise,
    list_opportunities,
)
from backend.services.opportunities.thread import (
    create_thread_for_user,
    delete_thread_for_user,
    get_or_create_thread_for_message,
    get_thread_for_user_or_raise,
    list_messages_for_thread,
    list_threads_for_user,
    load_recent_history,
    save_chat_exchange,
)

__all__ = [
    "list_opportunities",
    "get_opportunity_filters",
    "get_opportunity_or_raise",
    "ChatContextItem",
    "ChatServiceResult",
    "generate_opportunity_chat_response",
    "generate_opportunity_chat_response_stream",
    "list_threads_for_user",
    "create_thread_for_user",
    "get_thread_for_user_or_raise",
    "list_messages_for_thread",
    "load_recent_history",
    "get_or_create_thread_for_message",
    "save_chat_exchange",
    "delete_thread_for_user",
]
