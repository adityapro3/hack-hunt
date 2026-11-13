"""Service-layer package grouped by domain.

Domains:
- admin: admin-only orchestration and app-level configuration
- chat: chat generation, provider abstraction, and thread persistence helpers
- common: shared domain errors and cross-cutting primitives
- embeddings: embedding generation and backfill operations
- news: latest-news scraping ingestion, cleanup, and retrieval
- opportunities: opportunity query and cleanup operations
- users: user-scoped settings, bookmarks, and applications
"""

